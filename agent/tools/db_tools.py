import os
from typing import Optional
from langchain_community.utilities import SQLDatabase
from langchain_core.tools import tool
from sqlalchemy import create_engine

# 仅支持通过环境变量配置的 MySQL 数据库
DB_URL = os.getenv("DATABASE_URL")

def get_db():
    if not DB_URL:
        raise ValueError("环境变量 DATABASE_URL 未设置，请在 .env 文件中配置 MySQL 连接串。")
    return SQLDatabase.from_uri(DB_URL)

import json
import time
from sqlalchemy import text

@tool
def sql_query(query: str) -> str:
    """在数据库上执行 SQL 查询并返回 JSON 格式的结果列表。"""
    print(f"\n[SQL Query on {DB_URL}]: {query}\n")
    db = get_db()
    start_time = time.time()
    try:
        # 使用 sqlalchemy 直接执行以获取字典格式
        engine = db._engine
        with engine.connect() as connection:
            result = connection.execute(text(query))
            
            # 如果是 DDL/DML 语句，返回成功提示
            if not result.returns_rows:
                connection.commit()
                duration = time.time() - start_time
                print(f"[SQL Duration]: {duration:.2f}s")
                return json.dumps({"status": "success", "message": "Query executed successfully (no rows returned)"}, ensure_ascii=False)

            # 限制返回行数，防止大数据量导致 OOM 或 Token 溢出
            rows = []
            for i, row in enumerate(result):
                if i >= 1000:
                    break
                rows.append(dict(row._mapping))
            
            duration = time.time() - start_time
            print(f"[SQL Duration]: {duration:.2f}s, Rows: {len(rows)}")
            
            if not rows:
                return json.dumps({"warning": "Query returned 0 rows", "data": []}, ensure_ascii=False)
                
            return json.dumps(rows, ensure_ascii=False, default=str)
    except Exception as e:
        error_msg = str(e)
        duration = time.time() - start_time
        print(f"[SQL Error after {duration:.2f}s]: {error_msg}")
        return json.dumps({"error": error_msg}, ensure_ascii=False)

@tool
def get_db_schema() -> str:
    """获取数据库的表结构信息。"""
    db = get_db()
    return db.get_table_info()
