
import sqlite3
import os

db_path = r"C:\Users\Эльвина\Desktop\Видео\db.sqlite"
print(f"Checking {db_path}...")
if not os.path.exists(db_path):
    print(f"  Path does not exist.")
else:
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10")
        rows = cur.fetchall()
        print(f"  Success! Recent orders in {db_path}:")
        for row in rows:
            print(f"    ID: {row['id']}, Status: {row['status']}, Created: {row['created_at']}")
        conn.close()
    except Exception as e:
        print(f"  Error: {e}")
