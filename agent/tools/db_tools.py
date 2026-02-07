import os
from typing import Optional
from langchain_community.utilities import SQLDatabase
from langchain_core.tools import tool
from sqlalchemy import create_engine

# 默认使用环境变量中的数据库连接串，如果没有则使用本地 sqlite 作为演示
DB_URL = os.getenv("DATABASE_URL", "sqlite:///data/demo.db")

def get_db():
    # 确保目录存在
    if DB_URL.startswith("sqlite:///"):
        os.makedirs("data", exist_ok=True)
    return SQLDatabase.from_uri(DB_URL)

import json
from sqlalchemy import text

@tool
def sql_query(query: str) -> str:
    """在数据库上执行 SQL 查询并返回 JSON 格式的结果列表。"""
    print(f"\n[SQL Query]: {query}\n")
    db = get_db()
    try:
        # 使用 sqlalchemy 直接执行以获取字典格式
        engine = db._engine
        with engine.connect() as connection:
            result = connection.execute(text(query))
            # 限制返回行数，防止大数据量导致 OOM 或 Token 溢出
            rows = []
            for i, row in enumerate(result):
                if i >= 1000:
                    break
                rows.append(dict(row._mapping))
            return json.dumps(rows, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@tool
def get_db_schema() -> str:
    """获取数据库的表结构信息。"""
    db = get_db()
    return db.get_table_info()
