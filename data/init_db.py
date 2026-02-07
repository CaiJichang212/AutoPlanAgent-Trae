import sqlite3
import os

def init_demo_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect("data/demo.db")
    cursor = conn.cursor()
    
    # 创建销售数据表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY,
        product_name TEXT,
        category TEXT,
        amount REAL,
        sale_date DATE
    )
    ''')
    
    # 插入一些测试数据
    sample_data = [
        ('iPhone 15', 'Electronics', 8000, '2023-01-15'),
        ('MacBook Pro', 'Electronics', 15000, '2023-02-20'),
        ('iPad Air', 'Electronics', 5000, '2023-03-10'),
        ('T-Shirt', 'Apparel', 100, '2023-01-05'),
        ('Jeans', 'Apparel', 300, '2023-02-15'),
        ('Coffee Maker', 'Home', 500, '2023-04-01'),
        ('Desk Lamp', 'Home', 150, '2023-05-12'),
        ('AirPods', 'Electronics', 1200, '2023-06-20'),
        ('Nike Shoes', 'Apparel', 800, '2023-07-15'),
        ('Yoga Mat', 'Sports', 200, '2023-08-01')
    ]
    
    cursor.executemany('INSERT INTO sales (product_name, category, amount, sale_date) VALUES (?, ?, ?, ?)', sample_data)
    
    conn.commit()
    conn.close()
    print("Demo database initialized.")

if __name__ == "__main__":
    init_demo_db()
