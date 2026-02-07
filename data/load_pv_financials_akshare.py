import argparse
import datetime as dt
import os
import sys
import time
from typing import Dict, List

import pandas as pd
from sqlalchemy import create_engine, text, inspect


def _import_akshare():
    try:
        import akshare as ak  # type: ignore
    except Exception as exc:
        raise RuntimeError("Missing dependency: akshare. Install with pip install -e .[data]") from exc
    return ak


def _build_engine() -> object:
    url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    if not url:
        host = os.getenv("MYSQL_HOST")
        user = os.getenv("MYSQL_USER")
        password = os.getenv("MYSQL_PASSWORD")
        db = os.getenv("MYSQL_DB")
        port = os.getenv("MYSQL_PORT", "3306")
        if not all([host, user, password, db]):
            raise RuntimeError("MySQL connection info missing. Set DATABASE_URL or MYSQL_URL or MYSQL_HOST/USER/PASSWORD/DB.")
        url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
    engine = create_engine(url, pool_pre_ping=True)
    return engine


def _daterange(start_year: int, end_year: int, annual_only: bool) -> List[str]:
    dates = []
    for y in range(start_year, end_year + 1):
        if annual_only:
            dates.append(f"{y}1231")
        else:
            dates.extend([f"{y}0331", f"{y}0630", f"{y}0930", f"{y}1231"])
    return dates


def _safe_call(ak, func_names: List[str], **kwargs):
    last_exc = None
    for name in func_names:
        if hasattr(ak, name):
            try:
                return getattr(ak, name)(**kwargs)
            except Exception as exc:
                last_exc = exc
                continue
    if last_exc:
        raise last_exc
    raise AttributeError(f"None of the functions exist: {func_names}")


def _get_code_map(ak) -> pd.DataFrame:
    try:
        df = _safe_call(ak, ["stock_info_a_code_name"])
        df = df.rename(columns={"code": "代码", "name": "名称"})
        return df[["代码", "名称"]]
    except Exception:
        pass

    frames = []
    for func, col_code, col_name, kwargs in [
        ("stock_info_sh_name_code", "代码", "简称", {"indicator": "主板A股"}),
        ("stock_info_sh_name_code", "代码", "简称", {"indicator": "科创板"}),
        ("stock_info_sz_name_code", "A股代码", "A股简称", {}),
        ("stock_info_bj_name_code", "证券代码", "证券简称", {}),
    ]:
        if hasattr(ak, func):
            try:
                df = getattr(ak, func)(**kwargs) if kwargs else getattr(ak, func)()
                if col_code in df.columns and col_name in df.columns:
                    frames.append(df[[col_code, col_name]].rename(columns={col_code: "代码", col_name: "名称"}))
            except Exception:
                continue
    if not frames:
        raise RuntimeError("Failed to fetch stock code/name list from akshare.")
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def _match_codes(code_map: pd.DataFrame, company_names: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    code_map["名称"] = code_map["名称"].astype(str)
    code_map["代码"] = code_map["代码"].astype(str)
    for name in company_names:
        exact = code_map[code_map["名称"] == name]
        if len(exact) == 1:
            code = exact.iloc[0]["代码"]
            mapping[name] = code.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
            continue
        fuzzy = code_map[code_map["名称"].str.contains(name)]
        if len(fuzzy) == 1:
            code = fuzzy.iloc[0]["代码"]
            mapping[name] = code.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
            continue
        if len(fuzzy) > 1:
            print(f"[WARN] Multiple matches for {name}: {fuzzy['代码'].tolist()} / {fuzzy['名称'].tolist()}")
        else:
            print(f"[WARN] No code match for {name}")
    return mapping


def _filter_targets(df: pd.DataFrame, codes: List[str]) -> pd.DataFrame:
    if "股票代码" in df.columns:
        key = "股票代码"
    elif "代码" in df.columns:
        key = "代码"
    else:
        return df.iloc[0:0]
    return df[df[key].astype(str).isin(codes)].copy()


def _ensure_report_date(df: pd.DataFrame, report_date: str) -> pd.DataFrame:
    df["report_date"] = report_date
    return df


def _pick_col(df: pd.DataFrame, candidates: List[str]) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    return ""


def _clean_numeric(series: pd.Series) -> pd.Series:
    cleaned = series.astype(str)
    cleaned = cleaned.str.replace(",", "", regex=False)
    cleaned = cleaned.str.replace("%", "", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")


def _to_billion(series: pd.Series) -> pd.Series:
    numeric = _clean_numeric(series)
    if numeric.dropna().empty:
        return numeric
    max_val = numeric.dropna().abs().max()
    if max_val > 1e6:
        return numeric / 1e8
    return numeric


def _ensure_pv_financials_table(engine, table: str) -> None:
    sql = f"""
    CREATE TABLE IF NOT EXISTS `{table}` (
        id INTEGER AUTO_INCREMENT PRIMARY KEY,
        company_name VARCHAR(100) NOT NULL,
        stock_code VARCHAR(20),
        industry_role VARCHAR(255),
        report_period VARCHAR(50),
        revenue_billion REAL,
        net_profit_billion REAL,
        revenue_growth_pct REAL,
        net_profit_growth_pct REAL,
        gross_margin_pct REAL,
        on_hand_orders_billion REAL,
        update_date DATE
    )
    """
    with engine.begin() as conn:
        conn.execute(text(sql))


def _build_pv_financials_frame(df: pd.DataFrame, report_date: str, mapping: Dict[str, str]) -> pd.DataFrame:
    if df.empty:
        return df.iloc[0:0]
    code_to_name = {v: k for k, v in mapping.items()}
    name_col = _pick_col(df, ["股票简称", "股票名称", "公司简称", "公司名称", "名称"])
    code_col = _pick_col(df, ["股票代码", "代码"])
    revenue_col = _pick_col(df, ["营业收入", "营业收入-营业收入", "营业总收入", "主营业务收入"])
    net_profit_col = _pick_col(df, ["净利润", "净利润-净利润", "归属净利润", "归母净利润"])
    revenue_growth_col = _pick_col(df, ["营业收入-同比增长", "营业收入同比增长率", "营收同比增长"])
    net_profit_growth_col = _pick_col(df, ["净利润-同比增长", "净利润同比增长率", "净利同比增长"])
    gross_margin_col = _pick_col(df, ["销售毛利率", "毛利率"])

    stock_codes = df[code_col].astype(str).str.replace(".SZ", "", regex=False).str.replace(".SH", "", regex=False).str.replace(".BJ", "", regex=False) if code_col else pd.Series([], dtype=str)
    company_names = df[name_col].astype(str) if name_col else stock_codes.map(code_to_name).fillna("")

    revenue = _to_billion(df[revenue_col]) if revenue_col else pd.Series([], dtype=float)
    net_profit = _to_billion(df[net_profit_col]) if net_profit_col else pd.Series([], dtype=float)
    revenue_growth = _clean_numeric(df[revenue_growth_col]) if revenue_growth_col else pd.Series([], dtype=float)
    net_profit_growth = _clean_numeric(df[net_profit_growth_col]) if net_profit_growth_col else pd.Series([], dtype=float)
    gross_margin = _clean_numeric(df[gross_margin_col]) if gross_margin_col else pd.Series([], dtype=float)

    result = pd.DataFrame({
        "company_name": company_names,
        "stock_code": stock_codes,
        "industry_role": None,
        "report_period": report_date,
        "revenue_billion": revenue,
        "net_profit_billion": net_profit,
        "revenue_growth_pct": revenue_growth,
        "net_profit_growth_pct": net_profit_growth,
        "gross_margin_pct": gross_margin,
        "on_hand_orders_billion": None,
        "update_date": dt.date.today().isoformat()
    })
    return result


def _upsert_pv_financials(engine, table: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    with engine.begin() as conn:
        for report_period in df["report_period"].dropna().unique().tolist():
            codes = df["stock_code"].dropna().astype(str).unique().tolist()
            if codes:
                placeholders = ",".join([f":c{i}" for i in range(len(codes))]) or "''"
                params = {f"c{i}": code for i, code in enumerate(codes)}
                params["report_period"] = report_period
                sql = f"DELETE FROM `{table}` WHERE report_period = :report_period AND stock_code IN ({placeholders})"
                conn.execute(text(sql), params)
    df.to_sql(table, engine, if_exists="append", index=False, method="multi")


def _upsert_table(engine, table: str, df: pd.DataFrame, report_date: str, codes: List[str]) -> None:
    if df.empty:
        return
    insp = inspect(engine)
    if insp.has_table(table):
        code_col = "股票代码" if "股票代码" in df.columns else ("代码" if "代码" in df.columns else None)
        if code_col:
            placeholders = ",".join([f":c{i}" for i in range(len(codes))]) or "''"
            params = {f"c{i}": code for i, code in enumerate(codes)}
            params["report_date"] = report_date
            sql = f"DELETE FROM `{table}` WHERE report_date = :report_date AND `{code_col}` IN ({placeholders})"
            with engine.begin() as conn:
                conn.execute(text(sql), params)
    df.to_sql(table, engine, if_exists="append", index=False, method="multi")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load PV company financials from Eastmoney via AkShare into MySQL")
    parser.add_argument(
        "--companies",
        nargs="+",
        default=["迈为股份", "捷佳伟创", "拉普拉斯", "奥特维", "晶盛机电", "连城数控"],
        help="Company names to load",
    )
    parser.add_argument("--start-year", type=int, default=dt.datetime.now().year - 6)
    parser.add_argument("--end-year", type=int, default=dt.datetime.now().year - 1)
    parser.add_argument("--annual-only", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.6)
    parser.add_argument("--table-prefix", default="test_")
    parser.add_argument("--pv-table", default="pv_financials")
    args = parser.parse_args()

    ak = _import_akshare()
    engine = _build_engine()

    code_map = _get_code_map(ak)
    mapping = _match_codes(code_map, args.companies)
    if not mapping:
        raise SystemExit("No company codes matched. Please provide correct company names.")

    company_df = pd.DataFrame(
        [{"company_name": k, "stock_code": v} for k, v in mapping.items()]
    )
    company_df.to_sql(f"{args.table_prefix}company", engine, if_exists="replace", index=False)

    dates = _daterange(args.start_year, args.end_year, args.annual_only)
    codes = list(mapping.values())

    tasks = [
        ("yjbb", ["stock_yjbb_em", "stock_em_yjbb"]),
        ("zcfz", ["stock_em_zcfz", "stock_zcfz_em", "stock_em_zcfz_report"]),
        ("lrb", ["stock_em_lrb", "stock_lrb_em", "stock_em_lrb_report"]),
        ("xjll", ["stock_xjll_em", "stock_em_xjll", "stock_em_xjll_report"]),
    ]

    for report_date in dates:
        for short, func_names in tasks:
            try:
                df = _safe_call(ak, func_names, date=report_date)
            except Exception as exc:
                print(f"[WARN] {short} {report_date} fetch failed: {exc}")
                continue
            df = _filter_targets(df, codes)
            df = _ensure_report_date(df, report_date)
            table = f"{args.table_prefix}em_{short}"
            _upsert_table(engine, table, df, report_date, codes)
            if short == "yjbb":
                _ensure_pv_financials_table(engine, args.pv_table)
                pv_df = _build_pv_financials_frame(df, report_date, mapping)
                _upsert_pv_financials(engine, args.pv_table, pv_df)
            print(f"[OK] {table} {report_date} rows={len(df)}")
            time.sleep(args.sleep)


if __name__ == "__main__":
    main()
