
import sqlite3
import os

db_paths = [
    r"C:\Users\Эльвина\Desktop\бот\db.sqlite",
    r"C:\Users\Эльвина\Desktop\botTon\db.sqlite",
    r"C:\Users\Эльвина\Desktop\botTon_updated\db.sqlite",
]

for db_path in db_paths:
    print(f"Checking {db_path}...")
    if not os.path.exists(db_path):
        print(f"  Path does not exist.")
        continue
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
        if cur.fetchone():
            cur = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 5")
            rows = cur.fetchall()
            print(f"  Success! Recent orders in {db_path}:")
            for row in rows:
                print(f"    ID: {row['id']}, Status: {row['status']}")
                if row['id'] == 84:
                    print("    FOUND ORDER 84!")
        else:
            print(f"  Table 'orders' not found.")
        conn.close()
    except Exception as e:
        print(f"  Error: {e}")
