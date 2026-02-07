import mysql.connector
import json
import os
from datetime import date

def setup_database():
    # 数据库配置
    config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'shsh123',
        'database': 'test_trae'
    }
    
    # 建立连接（先不指定数据库以确保能创建它）
    try:
        conn = mysql.connector.connect(
            host=config['host'],
            port=config['port'],
            user=config['user'],
            password=config['password']
        )
        cursor = conn.cursor()
        
        # 创建数据库
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config['database']} CHARACTER SET utf8mb4")
        cursor.execute(f"USE {config['database']}")
        
        # 创建光伏企业财报表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pv_financials (
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
        ''')
        
        # 准备数据 (基于搜索到的 2024H1 数据)
        # 注意：部分缺失数据设为 None
        today = date.today().isoformat()
        sample_data = [
            # 迈为股份：HJT整线设备龙头
            ('迈为股份', '300751', 'HJT整线设备龙头', '2024H1', 4.87, 0.65, 69.74, None, 28.0, None, today),
            # 捷佳伟创：TOPCon及钙钛矿设备
            ('捷佳伟创', '300724', 'TOPCon及钙钛矿设备', '2024H1', 66.22, 12.26, 62.19, 63.15, 31.62, 426.61, today),
            # 奥特维：全链条覆盖
            ('奥特维', '688516', '全链条覆盖(串焊机龙头)', '2024H1', 4.42, 0.77, 75.48, None, None, 143.41, today),
            # 晶盛机电：超薄硅片设备 (单晶炉)
            ('晶盛机电', '300316', '单晶炉/超薄硅片设备', '2024H1', 101.47, 20.96, None, -5.0, 33.0, None, today),
            # 连城数控：超薄硅片设备
            ('连城数控', '920368', '超薄硅片设备', '2024H1', 25.31, 3.21, 33.79, 38.21, 32.43, None, today),
            # 拉普拉斯：TOPCon及钙钛矿设备 (新上市)
            ('拉普拉斯', '688726', 'TOPCon及钙钛矿设备', '2024H1', 5.0, None, None, None, None, None, today)
        ]
        
        # 插入数据
        insert_query = '''
        INSERT INTO pv_financials 
        (company_name, stock_code, industry_role, report_period, revenue_billion, net_profit_billion, 
         revenue_growth_pct, net_profit_growth_pct, gross_margin_pct, on_hand_orders_billion, update_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        
        cursor.executemany(insert_query, sample_data)
        
        conn.commit()
        print(f"成功在 MySQL 数据库 '{config['database']}' 中创建表并插入了 {len(sample_data)} 条光伏企业财报数据。")
        
    except mysql.connector.Error as err:
        print(f"数据库操作失败: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    setup_database()
