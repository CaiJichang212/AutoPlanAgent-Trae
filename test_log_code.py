
import json
import pandas as pd
import numpy as np

# Mock context
context = {
    "step2": [
        {"company_name": "奥特维", "stock_code": "688516", "industry_role": "全链条覆盖(串焊机龙头)", "report_period": "2024H1", "revenue_billion": 4.42, "net_profit_billion": 0.77, "revenue_growth_pct": 75.48, "net_profit_growth_pct": None, "gross_margin_pct": None, "on_hand_orders_billion": 143.41}
    ]
}

# Code from log
import json
import pandas as pd
import numpy as np

# 从上下文获取上一步的处理结果
step2_data = context['step2']

# 转换为 DataFrame
df = pd.DataFrame(step2_data)

# 检查是否为空数据
if df.empty:
    print(json.dumps({"error": "No data found in step2, cannot proceed with cleaning."}))
    exit()

# 1. 处理缺失值：对于数值型字段，使用中位数填充（避免均值受异常值影响）
numeric_columns = [
    'revenue_billion',
    'net_profit_billion',
    'revenue_growth_pct',
    'net_profit_growth_pct',
    'gross_margin_pct',
    'on_hand_orders_billion'
]

for col in numeric_columns:
    if col in df.columns:
        # 用中位数填充缺失值
        median_val = df[col].median()
        df[col] = df[col].fillna(median_val)

# 2. 异常值处理：使用 IQR 法检测并处理异常值（仅对数值列）
def detect_outliers_iqr(series):
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    return (series < lower_bound) | (series > upper_bound)

# 只对有足够有效数据的列进行异常值处理
for col in numeric_columns:
    if col not in df.columns or df[col].isna().all():
        continue
    # 去除 NaN 后计算
    clean_series = df[col].dropna()
    if len(clean_series) < 2:
        continue  # 数据太少无法判断异常
    outliers = detect_outliers_iqr(clean_series)
    if outliers.any():
        # 用中位数替换异常值
        median_val = clean_series.median()
        df.loc[outliers.index, col] = median_val

# 3. 标准化字段格式
# - report_period: 统一为 'YYYYH1' / 'YYYYQ4' 格式（当前已是标准格式，无需更改）
# - industry_role: 去除前后空格
if 'industry_role' in df.columns:
    df['industry_role'] = df['industry_role'].astype(str).str.strip()

# - company_name, stock_code: 去除多余空格
if 'company_name' in df.columns:
    df['company_name'] = df['company_name'].astype(str).str.strip()
if 'stock_code' in df.columns:
    df['stock_code'] = df['stock_code'].astype(str).str.strip()

# 4. 确保所有数值列是浮点类型
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

# 5. 验证关键字段的合理性（如毛利率不应为负或过大）
if 'gross_margin_pct' in df.columns:
    # 合理范围：0% ~ 100%
    invalid_margin = (df['gross_margin_pct'] < 0) | (df['gross_margin_pct'] > 100)
    if invalid_margin.any():
        # 将不合理值设为 NaN，后续由中位数补全
        df.loc[invalid_margin, 'gross_margin_pct'] = np.nan
        # 再次用中位数填充
        median_val = df['gross_margin_pct'].median()
        df['gross_margin_pct'] = df['gross_margin_pct'].fillna(median_val)

# 6. 生成清洗后的结果
cleaned_data = df.to_dict(orient='records')

# 输出最终结果
print(json.dumps({
    "cleaned_data": cleaned_data,
    "summary": {
        "total_records": len(df),
        "missing_values_after_cleaning": df.isnull().sum().to_dict(),
        "outlier_replaced_count": sum((df[col].isna() & df[col].notna()).sum() for col in numeric_columns)
    }
}, default=str))
