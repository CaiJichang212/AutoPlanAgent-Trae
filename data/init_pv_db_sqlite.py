import sqlite3
import os
from datetime import date

def init_pv_sqlite():
    os.makedirs("data", exist_ok=True)
    db_path = "data/pv_data.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建光伏企业财报表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pv_financials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        stock_code TEXT,
        industry_role TEXT,
        report_period TEXT,
        revenue_billion REAL,
        net_profit_billion REAL,
        revenue_growth_pct REAL,
        net_profit_growth_pct REAL,
        gross_margin_pct REAL,
        on_hand_orders_billion REAL,
        update_date DATE
    )
    ''')
    
    # 准备数据 (基于搜索到的 2024H1 数据)
    today = date.today().isoformat()
    sample_data = [
        ('迈为股份', '300751', 'HJT整线设备龙头', '2024H1', 4.87, 0.65, 69.74, None, 28.0, None, today),
        ('捷佳伟创', '300724', 'TOPCon及钙钛矿设备', '2024H1', 66.22, 12.26, 62.19, 63.15, 31.62, 426.61, today),
        ('奥特维', '688516', '全链条覆盖(串焊机龙头)', '2024H1', 4.42, 0.77, 75.48, None, 24.0, 143.41, today),
        ('晶盛机电', '300316', '单晶炉/超薄硅片设备', '2024H1', 101.47, 20.96, None, -5.0, 33.0, None, today),
        ('连城数控', '920368', '超薄硅片设备', '2024H1', 25.31, 3.21, 33.79, 38.21, 32.43, None, today),
        ('拉普拉斯', '688726', 'TOPCon及钙钛矿设备', '2024H1', 5.0, None, None, None, 25.0, None, today)
    ]
    
    cursor.executemany('''
    INSERT INTO pv_financials 
    (company_name, stock_code, industry_role, report_period, revenue_billion, net_profit_billion, 
     revenue_growth_pct, net_profit_growth_pct, gross_margin_pct, on_hand_orders_billion, update_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', sample_data)
    
    conn.commit()
    conn.close()
    print(f"成功初始化 SQLite 数据库: {db_path}，已插入 {len(sample_data)} 条光伏企业数据。")

if __name__ == "__main__":
    init_pv_sqlite()
