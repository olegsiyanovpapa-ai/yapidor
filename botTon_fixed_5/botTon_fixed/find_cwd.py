
import psutil
import sys

pid = 10316
try:
    p = psutil.Process(pid)
    print(f"PID: {pid}")
    print(f"Name: {p.name()}")
    print(f"CWD: {p.cwd()}")
    print(f"CommandLine: {p.cmdline()}")
except Exception as e:
    print(f"Error: {e}")
