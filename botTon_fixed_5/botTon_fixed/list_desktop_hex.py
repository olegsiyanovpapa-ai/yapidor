
import os

desktop = r"C:\Users\Эльвина\Desktop"
for item in os.listdir(desktop):
    full_path = os.path.join(desktop, item)
    if os.path.isdir(full_path):
        print(f"Name: {item}")
        print(f"Hex: {item.encode('utf-8').hex()}")
        if os.path.exists(os.path.join(full_path, "db.sqlite")):
            print(f"  --> FOUND db.sqlite in {item}")
