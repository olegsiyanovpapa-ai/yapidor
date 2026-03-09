import aiosqlite
from datetime import datetime
from .config import DB_NAME

_db = None

async def get_db():
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_NAME)
        _db.row_factory = aiosqlite.Row 
    return _db

async def init_db():
    db = await get_db()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            rub_amount INTEGER,
            ton_amount REAL,
            rate REAL,
            status TEXT,
            pay_method TEXT,
            payment_id TEXT,
            payment_url TEXT,
            user_wallet TEXT,
            expires_at TEXT,
            created_at TEXT,
            paid_at TEXT,
            type TEXT DEFAULT 'BUY',
            delivery_error TEXT
        )
    """)
    
    # Migration for existing tables
    try:
        await db.execute("ALTER TABLE orders ADD COLUMN type TEXT DEFAULT 'BUY'")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE orders ADD COLUMN delivery_error TEXT")
    except Exception:
        pass

    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            default_wallet TEXT,
            referrer_id INTEGER,
            ref_balance REAL DEFAULT 0,
            ref_currency_pref TEXT,
            ref_count INTEGER DEFAULT 0,
            ref_volume REAL DEFAULT 0,
            created_at TEXT
        )
    """)
    
    # Migrations
    columns = [
        ("username", "TEXT"),
        ("referrer_id", "INTEGER"),
        ("ref_balance", "REAL DEFAULT 0"),
        ("ref_currency_pref", "TEXT"),
        ("ref_count", "INTEGER DEFAULT 0"),
        ("ref_volume", "REAL DEFAULT 0")
    ]
    for col_name, col_type in columns:
        try:
            await db.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS ton_connect_sessions (
            user_id INTEGER PRIMARY KEY,
            wallet_address TEXT,
            session_data TEXT,
            connected_at TEXT,
            last_used_at TEXT
        )
    """)
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS global_stats (
            key TEXT PRIMARY KEY,
            value REAL DEFAULT 0
        )
    """)
    
    # Initialize global stats if empty
    await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status)")
    
    cur = await db.execute("SELECT COUNT(*) FROM global_stats")
    row = await cur.fetchone()
    if row and row[0] == 0:
        # Seed from existing orders
        cur_ton = await db.execute("SELECT SUM(ton_amount) FROM orders WHERE status='PAID' AND type='BUY'")
        ton_bought_row = await cur_ton.fetchone()
        ton_bought = ton_bought_row[0] if (ton_bought_row and ton_bought_row[0]) else 0
        
        cur_stars = await db.execute("SELECT SUM(ton_amount) FROM orders WHERE status='PAID' AND type='BUY_STARS'")
        stars_bought_row = await cur_stars.fetchone()
        stars_bought = stars_bought_row[0] if (stars_bought_row and stars_bought_row[0]) else 0

        cur_premium = await db.execute("SELECT COUNT(*) FROM orders WHERE status='PAID' AND type='BUY_PREMIUM'")
        premium_bought = (await cur_premium.fetchone())[0] or 0

        cur_gifts = await db.execute("SELECT COUNT(*) FROM orders WHERE status='PAID' AND type='BUY_GIFT'")
        gifts_bought = (await cur_gifts.fetchone())[0] or 0
        
        await db.execute("INSERT OR IGNORE INTO global_stats (key, value) VALUES ('ton_bought', ?)", (ton_bought,))
        await db.execute("INSERT OR IGNORE INTO global_stats (key, value) VALUES ('stars_bought', ?)", (stars_bought,))
        await db.execute("INSERT OR IGNORE INTO global_stats (key, value) VALUES ('premium_bought', ?)", (premium_bought,))
        await db.execute("INSERT OR IGNORE INTO global_stats (key, value) VALUES ('gifts_bought', ?)", (gifts_bought,))
        await db.commit()
    else:
        await db.execute("INSERT OR IGNORE INTO global_stats (key, value) VALUES ('gifts_bought', 0)")
        await db.commit()

    await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    await db.commit()

async def get_user_wallet(user_id: int):
    db = await get_db()
    cur = await db.execute("SELECT default_wallet FROM users WHERE user_id = ?", (user_id,))
    row = await cur.fetchone()
    return row[0] if row else None

_global_stats_cache = {
    "stats": None,
    "timestamp": 0
}

async def get_global_stats():
    """Get global statistics for the main menu with 1-minute caching"""
    import time
    current_time = time.time()
    
    if _global_stats_cache["stats"] and (current_time - _global_stats_cache["timestamp"] < 60):
        return _global_stats_cache["stats"]
        
    db = await get_db()
    try:
        cur = await db.execute("SELECT key, value FROM global_stats")
        rows = await cur.fetchall()
        stats = {row[0]: row[1] for row in rows}
        
        result = {
            "ton_bought": stats.get("ton_bought", 0),
            "stars_bought": int(stats.get("stars_bought", 0)),
            "premium_bought": int(stats.get("premium_bought", 0)),
            "gifts_bought": int(stats.get("gifts_bought", 0))
        }
        
        _global_stats_cache["stats"] = result
        _global_stats_cache["timestamp"] = current_time
        return result
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error fetching global stats: {e}")
        return _global_stats_cache["stats"] or {"ton_bought": 0, "stars_bought": 0, "premium_bought": 0, "gifts_bought": 0}

def invalidate_global_stats_cache():
    _global_stats_cache["timestamp"] = 0
async def save_user(user_id: int, username: str = None, referrer_id: int = None):
    db = await get_db()
    now = datetime.utcnow().isoformat()
    
    # Check if user already exists to determine if we should increment ref_count
    cur = await db.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    existing_user = await cur.fetchone()
    
    if referrer_id and not existing_user:
        # New user with a referrer
        await db.execute("""
            INSERT INTO users (user_id, username, referrer_id, created_at, ref_count, ref_volume)
            VALUES (?, ?, ?, ?, 0, 0)
        """, (user_id, username, referrer_id, now))
        
        # Increment referrer's count
        await db.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?", (referrer_id,))
    elif not existing_user:
        # New user without a referrer
        await db.execute("""
            INSERT INTO users (user_id, username, created_at, ref_count, ref_volume)
            VALUES (?, ?, ?, 0, 0)
        """, (user_id, username, now))
    else:
        # Existing user - just update username
        await db.execute("""
            UPDATE users SET username = COALESCE(?, username) WHERE user_id = ?
        """, (username, user_id))
        
    await db.commit()

async def save_user_wallet(user_id: int, wallet: str):
    db = await get_db()
    await db.execute("""
        INSERT INTO users (user_id, default_wallet, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET 
            default_wallet = excluded.default_wallet
    """, (user_id, wallet, datetime.utcnow().isoformat()))
    await db.commit()

async def delete_user_wallet(user_id: int):
    """Clear manual wallet address for user"""
    db = await get_db()
    await db.execute("UPDATE users SET default_wallet = NULL WHERE user_id = ?", (user_id,))
    await db.commit()

async def create_order(user_id, rub, ton, rate, wallet, expires, order_type="BUY", payment_id=None):
    db = await get_db()
    cur = await db.execute("""
        INSERT INTO orders
        (user_id, rub_amount, ton_amount, rate, status, pay_method, user_wallet, expires_at, created_at, type, payment_id)
        VALUES (?, ?, ?, ?, 'WAIT', 'PENDING', ?, ?, ?, ?, ?)
    """, (
        user_id, rub, ton, rate, 
        wallet, expires, datetime.utcnow().isoformat(), order_type, payment_id
    ))
    order_id = cur.lastrowid
    await db.commit()
    return order_id

async def update_order_payment(order_id, method, url):
    db = await get_db()
    await db.execute("UPDATE orders SET pay_method=?, payment_url=? WHERE id=?", 
                     (method, url, order_id))
    await db.commit()

async def get_last_orders(user_id, limit=5):
    db = await get_db()
    cur = await db.execute("SELECT id, ton_amount, rub_amount, status, type FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))
    return await cur.fetchall()

async def get_order_details(order_id: int):
    """Get complete order details by order ID"""
    db = await get_db()
    cur = await db.execute(
        "SELECT user_id, rub_amount, ton_amount, rate, user_wallet, type, payment_id FROM orders WHERE id=?",
        (order_id,)
    )
    row = await cur.fetchone()
    if row:
        return {
            "user_id": row[0],
            "rub_amount": row[1],
            "ton_amount": row[2],
            "rate": row[3],
            "user_wallet": row[4],
            "type": row[5],
            "payment_id": row[6]
        }
    return None


# TON Connect Session Management
async def save_ton_connect_session(user_id: int, wallet_address: str, session_data: str):
    """Save TON Connect wallet session"""
    import json
    
    # If wallet_address is not provided, try to extract it from session_data
    if not wallet_address and session_data:
        try:
            data = json.loads(session_data)
            conn_info = data.get('ton-connect-storage_bridge-connection')
            if conn_info:
                conn_dict = json.loads(conn_info)
                # Attempt to find the address in the connect event payload
                addr = conn_dict.get('connect_event', {}).get('payload', {}).get('items', [{}])[0].get('address')
                if addr:
                    wallet_address = addr
        except:
            pass

    db = await get_db()
    now = datetime.utcnow().isoformat()
    if wallet_address:
        await db.execute("""
            INSERT OR REPLACE INTO ton_connect_sessions 
            (user_id, wallet_address, session_data, connected_at, last_used_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, wallet_address, session_data, now, now))
    else:
        await db.execute("""
            INSERT INTO ton_connect_sessions (user_id, session_data, connected_at, last_used_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                session_data = excluded.session_data,
                last_used_at = excluded.last_used_at
        """, (user_id, session_data, now, now))
    await db.commit()

async def get_ton_connect_session(user_id: int):
    """Get TON Connect session for user"""
    db = await get_db()
    cur = await db.execute(
        "SELECT wallet_address, session_data FROM ton_connect_sessions WHERE user_id = ?", 
        (user_id,)
    )
    row = await cur.fetchone()
    if row:
        # Update last_used_at
        await db.execute(
            "UPDATE ton_connect_sessions SET last_used_at = ? WHERE user_id = ?",
            (datetime.utcnow().isoformat(), user_id)
        )
        await db.commit()
        return {"wallet_address": row[0], "session_data": row[1]}
    return None

async def delete_ton_connect_session(user_id: int):
    """Delete TON Connect session (disconnect wallet)"""
    db = await get_db()
    await db.execute("DELETE FROM ton_connect_sessions WHERE user_id = ?", (user_id,))
    await db.commit()

# --- Admin Methods ---

async def update_order_status(order_id: int, status: str):
    db = await get_db()
    now = datetime.utcnow().isoformat()
    
    # If order is being marked as PAID, update global stats
    if status == 'PAID':
        cur = await db.execute("SELECT type, ton_amount, status FROM orders WHERE id = ?", (order_id,))
        order = await cur.fetchone()
        if order and order[2] != 'PAID': # Avoid double counting
            order_type = order[0]
            amount = order[1]
            
            if order_type == 'BUY':
                await db.execute("UPDATE global_stats SET value = value + ? WHERE key = 'ton_bought'", (amount,))
            elif order_type == 'BUY_STARS':
                await db.execute("UPDATE global_stats SET value = value + ? WHERE key = 'stars_bought'", (amount,))
            elif order_type == 'BUY_PREMIUM':
                await db.execute("UPDATE global_stats SET value = value + 1 WHERE key = 'premium_bought'")
            elif order_type == 'BUY_GIFT':
                await db.execute("UPDATE global_stats SET value = value + 1 WHERE key = 'gifts_bought'")
        
        await db.execute("UPDATE orders SET status=?, paid_at=? WHERE id=?", (status, now, order_id))
    else:
        await db.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        
    await db.commit()

async def get_admin_stats():
    db = await get_db()
    # Count orders by status
    cur = await db.execute("SELECT status, COUNT(*), SUM(rub_amount), SUM(ton_amount) FROM orders GROUP BY status")
    rows = await cur.fetchall()
    
    # Calculate profit specifically for PAID orders
    p_cur = await db.execute("""
        SELECT 
            SUM(CASE WHEN type = 'BUY' THEN rub_amount * (0.25/1.25) ELSE 0 END) as buy_profit,
            SUM(CASE WHEN type = 'SELL' THEN rub_amount * (0.08/0.92) ELSE 0 END) as sell_profit,
            SUM(CASE WHEN type = 'BUY_PREMIUM' THEN rub_amount * (0.20/1.20) ELSE 0 END) as premium_profit,
            SUM(CASE WHEN type IN ('BUY_STARS', 'BUY_GIFT') THEN rub_amount * 0.15 ELSE 0 END) as stars_profit,
            SUM(CASE WHEN type = 'BUY' THEN rub_amount ELSE 0 END) as buy_rub,
            SUM(CASE WHEN type = 'SELL' THEN rub_amount ELSE 0 END) as sell_rub
        FROM orders 
        WHERE status = 'PAID'
    """)
    profit_row = await p_cur.fetchone()
    
    return {
        "by_status": rows,
        "profit": profit_row
    }

async def get_all_orders(status_filter=None, limit=50):
    db = await get_db()
    query = "SELECT id, user_id, rub_amount, ton_amount, status, type, created_at FROM orders"
    params = []
    if status_filter:
        query += " WHERE status = ?"
        params.append(status_filter)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    
    cur = await db.execute(query, tuple(params))
    return await cur.fetchall()

async def get_all_wallets():
    db = await get_db()
    # Get from users table
    cur1 = await db.execute("SELECT user_id, default_wallet FROM users WHERE default_wallet IS NOT NULL")
    wallets = await cur1.fetchall()
    
    # Get from TON Connect sessions (might be duplicates, we'll handle in code)
    cur2 = await db.execute("SELECT user_id, wallet_address FROM ton_connect_sessions")
    tc_wallets = await cur2.fetchall()
    
    return {"manual": wallets, "ton_connect": tc_wallets}

# --- Referral Program Methods ---

async def get_user_referral_data(user_id: int):
    db = await get_db()
    # Note: row_factory already set to Row in get_db()
    cur = await db.execute("""
        SELECT 
            u.ref_balance, 
            u.ref_currency_pref,
            (SELECT COUNT(*) FROM users WHERE referrer_id = u.user_id) as ref_count,
            (SELECT SUM(o.rub_amount) FROM orders o 
             JOIN users ur ON o.user_id = ur.user_id 
             WHERE ur.referrer_id = u.user_id AND o.status = 'PAID') as ref_volume
        FROM users u
        WHERE u.user_id = ?
    """, (user_id,))
    return await cur.fetchone()

async def update_ref_currency_pref(user_id: int, pref: str):
    db = await get_db()
    await db.execute("UPDATE users SET ref_currency_pref = ? WHERE user_id = ?", (pref, user_id))
    await db.commit()

async def accrue_referral_reward(buyer_id: int, profit_rub: float, volume_rub: float):
    if profit_rub <= 0: return None, 0
    
    reward = profit_rub * 0.08 # 8% of profit
    
    db = await get_db()
    # Find referrer
    cur = await db.execute("SELECT referrer_id FROM users WHERE user_id = ?", (buyer_id,))
    row = await cur.fetchone()
    if row and row[0]:
        referrer_id = row[0]
        await db.execute("""
            UPDATE users 
            SET ref_balance = ref_balance + ?, 
                ref_volume = ref_volume + ? 
            WHERE user_id = ?
        """, (reward, volume_rub, referrer_id))
        await db.commit()
        return referrer_id, reward
    return None, 0

async def deduct_ref_balance(user_id: int, amount_rub: float):
    db = await get_db()
    # Check if enough balance
    cur = await db.execute("SELECT ref_balance FROM users WHERE user_id = ?", (user_id,))
    row = await cur.fetchone()
    if row and row[0] >= amount_rub:
        await db.execute("UPDATE users SET ref_balance = ref_balance - ? WHERE user_id = ?", (amount_rub, user_id))
        await db.commit()
        return True
    return False

async def get_all_user_ids():
    db = await get_db()
    cur = await db.execute("SELECT user_id FROM users")
    rows = await cur.fetchall()
    return [row[0] for row in rows]

async def get_user_full_data(user_id: int):
    """Get full profile, referral stats, and last 10 orders for a user"""
    db = await get_db()
    # User & Referral Data
    cur_u = await db.execute("""
        SELECT *,
        (SELECT COUNT(*) FROM users WHERE referrer_id = u.user_id) as ref_count,
        (SELECT SUM(rub_amount) FROM orders WHERE user_id IN (SELECT user_id FROM users WHERE referrer_id = u.user_id) AND status = 'PAID') as ref_volume_manual
        FROM users u WHERE user_id = ?
    """, (user_id,))
    user = await cur_u.fetchone()
    if not user: return None
    
    # Last 10 orders
    cur_o = await db.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
    orders = await cur_o.fetchall()
    
    return {"user": user, "orders": orders}

async def get_orders_by_status_and_type(status: str, order_type: str = None, limit: int = 20):
    db = await get_db()
    query = "SELECT * FROM orders WHERE status = ?"
    params = [status]
    if order_type:
        query += " AND type = ?"
        params.append(order_type)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    
    cur = await db.execute(query, tuple(params))
    return await cur.fetchall()

async def get_top_buyers(limit: int = 10):
    db = await get_db()
    # Top users by purchase volume
    cur = await db.execute("""
        SELECT o.user_id, u.username, SUM(o.rub_amount) as total_rub 
        FROM orders o
        JOIN users u ON o.user_id = u.user_id
        WHERE o.status = 'PAID'
        GROUP BY o.user_id
        ORDER BY total_rub DESC
        LIMIT ?
    """, (limit,))
    return await cur.fetchall()

async def get_top_referrers(limit: int = 10):
    db = await get_db()
    cur = await db.execute("""
        SELECT u.user_id, u.username, COUNT(r.user_id) as ref_count
        FROM users u
        LEFT JOIN users r ON r.referrer_id = u.user_id
        GROUP BY u.user_id
        ORDER BY ref_count DESC
        LIMIT ?
    """, (limit,))
    return await cur.fetchall()

async def get_order_by_id(order_id: int):
    db = await get_db()
    cur = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    return await cur.fetchone()

async def clear_all_data():
    """Clear all orders and reset legacy referral columns for full cleanup."""
    db = await get_db()
    # Delete all orders
    await db.execute("DELETE FROM orders")
    # Reset legacy referral columns (kept in schema for compatibility)
    try:
        await db.execute("UPDATE users SET ref_balance = 0, ref_volume = 0, ref_count = 0, referrer_id = NULL")
    except Exception:
        pass
    await db.commit()

async def clear_orders_by_status(status: str):
    db = await get_db()
    await db.execute("DELETE FROM orders WHERE status = ?", (status,))
    await db.commit()

async def get_setting(key: str, default: str = None):
    db = await get_db()
    cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cur.fetchone()
    return row[0] if row else default
async def set_delivery_error(order_id: int, error_text: str):
    db = await get_db()
    await db.execute("UPDATE orders SET delivery_error = ? WHERE id = ?", (error_text, order_id))
    await db.commit()

async def get_failed_payouts(limit: int = 20):
    db = await get_db()
    # Orders that are PAID but NOT delivered (we'll use status=DELIVERED as indicator or status=PAID & delivery_error IS NOT NULL)
    # Actually, if we use status 'DELIVERED' for success, then 'PAID' orders are 'not delivered yet'.
    cur = await db.execute("""
        SELECT * FROM orders 
        WHERE status = 'PAID' AND delivery_error IS NOT NULL 
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    return await cur.fetchall()

async def get_undelivered_paid_count():
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'PAID'")
    row = await cur.fetchone()
    return row[0] if row else 0

async def set_setting(key: str, value: str):
    db = await get_db()
    await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    await db.commit()
