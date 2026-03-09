
import os

search_root = "C:\\Users\\Эльвина\\Desktop"
for root, dirs, files in os.walk(search_root):
    if "db.sqlite" in files:
        print(os.path.join(root, "db.sqlite"))
