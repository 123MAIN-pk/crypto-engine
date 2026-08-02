import time
import random
import sqlite3
from flask import Flask, jsonify, request

app = Flask(__name__)
DB_NAME = "exchange.db"

# ---------------------------------------------------------
# DATABASE INITIALIZATION
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # جدول سفارشات (Orderbook)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_pair TEXT,
            side TEXT,
            price REAL,
            amount REAL,
            status TEXT,
            timestamp INTEGER
        )
    ''')
    # جدول معاملات انجام شده (Trades)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_pair TEXT,
            price REAL,
            amount REAL,
            trade_type TEXT,
            timestamp INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# SPOT ENDPOINTS (Section A)
# ---------------------------------------------------------
ASSETS_DB = {
    "BTC": {"name": "Bitcoin", "unified_cryptoasset_id": "1", "can_withdraw": "true", "can_deposit": "true", "min_withdraw": "0.001", "max_withdraw": "100", "maker_fee": "0.001", "taker_fee": "0.0015"},
    "ETH": {"name": "Ethereum", "unified_cryptoasset_id": "1027", "can_withdraw": "true", "can_deposit": "true", "min_withdraw": "0.01", "max_withdraw": "1000", "maker_fee": "0.001", "taker_fee": "0.0015", "contractAddressUrl": "https://etherscan.io/token/0xc02aaa39b223fed8d0a0e5c4f27ead9083c756cc2", "contractAddress": "0xc02aaa39b223fed8d0a0e5c4f27ead9083c756cc2"},
    "USDT": {"name": "Tether", "unified_cryptoasset_id": "825", "can_withdraw": "true", "can_deposit": "true", "min_withdraw": "10.00", "max_withdraw": "100000", "maker_fee": "0.0", "taker_fee": "0.0"}
}

MARKETS = {
    "BTC_USDT": {"base_id": 1, "quote_id": 825, "price": 65000.0, "is_frozen": 0},
    "ETH_USDT": {"base_id": 1027, "quote_id": 825, "price": 3500.0, "is_frozen": 0}
}

@app.route('/summary', methods=['GET'])
def get_summary():
    summary_data = []
    for pair, info in MARKETS.items():
        base_price = info["price"]
        summary_data.append({
            "trading_pairs": pair,
            "last_price": str(base_price),
            "lowest_ask": str(round(base_price * 1.001, 4)),
            "highest_bid": str(round(base_price * 0.999, 4)),
            "base_volume": "1500.50",
            "quote_volume": str(round(1500.50 * base_price, 2)),
            "price_change_percent_24h": "2.45",
            "highest_price_24h": str(round(base_price * 1.05, 4)),
            "lowest_price_24h": str(round(base_price * 0.95, 4))
        })
    return jsonify(summary_data)

@app.route('/assets', methods=['GET'])
def get_assets():
    return jsonify(ASSETS_DB)

@app.route('/orderbook/<market_pair>', methods=['GET'])
def get_orderbook(market_pair):
    pair = market_pair.upper()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT price, amount FROM orders WHERE market_pair=? AND side='bid' AND status='open' ORDER BY price DESC", (pair,))
    bids = [[str(r[0]), str(r[1])] for r in cursor.fetchall()]
    
    cursor.execute("SELECT price, amount FROM orders WHERE market_pair=? AND side='ask' AND status='open' ORDER BY price ASC", (pair,))
    asks = [[str(r[0]), str(r[1])] for r in cursor.fetchall()]
    
    conn.close()

    # اگر دیتابیس خالی بود، داده ماک برمی‌گردونه
    if not bids and not asks and pair in MARKETS:
        p = MARKETS[pair]["price"]
        bids = [[str(round(p * 0.999, 2)), "1.5"]]
        asks = [[str(round(p * 1.001, 2)), "1.2"]]

    return jsonify({
        "timestamp": str(int(time.time() * 1000)),
        "bids": bids,
        "asks": asks
    })

# ثبت سفارش جدید و اتصال به موتور معامله (Matching Engine)
@app.route('/order', methods=['POST'])
def create_order():
    data = request.json
    pair = data.get("market_pair").upper()
    side = data.get("side").lower() # 'bid' (خرید) یا 'ask' (فروش)
    price = float(data.get("price"))
    amount = float(data.get("amount"))
    ts = int(time.time() * 1000)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # MATCHING ENGINE: بررسی برخورد سفارش خرید و فروش
    if side == 'bid':
        cursor.execute("SELECT id, price, amount FROM orders WHERE market_pair=? AND side='ask' AND status='open' AND price<=? ORDER BY price ASC", (pair, price))
        match = cursor.fetchone()
        if match:
            match_id, match_price, match_amount = match
            cursor.execute("UPDATE orders SET status='filled' WHERE id=?", (match_id,))
            cursor.execute("INSERT INTO trades (market_pair, price, amount, trade_type, timestamp) VALUES (?, ?, ?, 'buy', ?)", (pair, match_price, amount, ts))
            conn.commit()
            conn.close()
            return jsonify({"status": "filled", "matched_with_order": match_id, "price": match_price})

    elif side == 'ask':
        cursor.execute("SELECT id, price, amount FROM orders WHERE market_pair=? AND side='bid' AND status='open' AND price>=? ORDER BY price DESC", (pair, price))
        match = cursor.fetchone()
        if match:
            match_id, match_price, match_amount = match
            cursor.execute("UPDATE orders SET status='filled' WHERE id=?", (match_id,))
            cursor.execute("INSERT INTO trades (market_pair, price, amount, trade_type, timestamp) VALUES (?, ?, ?, 'sell', ?)", (pair, match_price, amount, ts))
            conn.commit()
            conn.close()
            return jsonify({"status": "filled", "matched_with_order": match_id, "price": match_price})

    # اگر معامله جور نشد، می‌ره تو Orderbook
    cursor.execute("INSERT INTO orders (market_pair, side, price, amount, status, timestamp) VALUES (?, ?, ?, ?, 'open', ?)", (pair, side, price, amount, ts))
    conn.commit()
    conn.close()
    return jsonify({"status": "open", "message": "Order added to orderbook"})

# ---------------------------------------------------------
# DERIVATIVES ENDPOINTS (Section B)
# ---------------------------------------------------------
@app.get('/contracts')
def get_contracts():
    """Endpoint B1 & B2: قراردادهای مشتقه و فیوچرز"""
    return jsonify([{
        "ticker_id": "BTC-PERPUSD",
        "base_currency": "BTC",
        "quote_currency": "USD",
        "last_price": "65000.0",
        "base_volume": "1200.5",
        "quote_volume": "78032500.0",
        "bid": "64990.0",
        "ask": "65010.0",
        "high": "66500.0",
        "low": "64100.0",
        "product_type": "Perpetual",
        "open_interest": "4500.25",
        "open_interest_usd": "292516250.0",
        "index_price": "65005.10",
        "funding_rate": "0.0001",
        "next_funding_rate_timestamp": str(int((time.time() + 28800) * 1000)),
        "contract_type": "Vanilla",
        "contract_price": "1.0",
        "contract_price_currency": "USD"
    }])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)


