
import os
import sqlite3

find_command = 'dir /s /b C:\\*.sqlite'
# I'll use os.walk to be more portably correct in Python if I can't rely on dir output format
search_roots = ["C:\\Users\\Эльвина", "C:\\"]

for start_dir in search_roots:
    print(f"Searching in {start_dir}...")
    for root, dirs, files in os.walk(start_dir):
        if "db.sqlite" in files:
            db_path = os.path.join(root, "db.sqlite")
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
                if cur.fetchone():
                    cur = conn.execute("SELECT * FROM orders WHERE id = 84")
                    row = cur.fetchone()
                    if row:
                        print(f"!!! FOUND ORDER 84 !!!")
                        print(f"  Path: {db_path}")
                        for key in row.keys():
                            print(f"    {key}: {row[key]}")
                        conn.close()
                        break
                conn.close()
            except Exception:
                pass
    else:
        continue
    break
