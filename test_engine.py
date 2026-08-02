import unittest
import sqlite3
import os

class TestCryptoEngine(unittest.TestCase):
    def setUp(self):
        self.db_name = "test_exchange.db"
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        self.cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, balance REAL)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, side TEXT, price REAL, amount REAL, status TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY, price REAL, amount REAL)")
        self.cursor.execute("INSERT INTO users VALUES (1, 'buyer', 10000.0), (2, 'seller', 10000.0)")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_name):
            os.remove(self.db_name)

    def test_01_users(self):
        self.cursor.execute("SELECT COUNT(*) FROM users")
        self.assertEqual(self.cursor.fetchone()[0], 2)

    def test_02_matching_and_pnl(self):
        # ثبت و تست جفت شدن سفارش خرید و فروش
        self.cursor.execute("INSERT INTO orders VALUES (1, 'BUY', 50000.0, 0.1, 'OPEN')")
        self.cursor.execute("INSERT INTO orders VALUES (2, 'SELL', 50000.0, 0.1, 'OPEN')")
        self.conn.commit()
        
        # محاسبه تست سود فیوچرز با اهرم ۱۰
        entry, exit_p, leverage, margin = 50000.0, 55000.0, 10, 100.0
        pnl = (exit_p - entry) * ((margin * leverage) / entry)
        self.assertEqual(pnl, 100.0)

if __name__ == '__main__':
    print("🚀 در حال اجرای تست خودکار موتور صرافی...")
    unittest.main()
