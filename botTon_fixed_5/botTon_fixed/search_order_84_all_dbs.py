
import os
import sqlite3

search_root = "C:\\Users\\Эльвина\\Desktop"
for root, dirs, files in os.walk(search_root):
    if "db.sqlite" in files:
        db_path = os.path.join(root, "db.sqlite")
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM orders WHERE id = 84")
            row = cur.fetchone()
            if row:
                print(f"!!! FOUND ORDER 84 IN: {db_path} !!!")
                for key in row.keys():
                    print(f"  {key}: {row[key]}")
            conn.close()
        except Exception as e:
            pass
