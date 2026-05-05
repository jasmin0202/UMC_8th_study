import os
from typing import List
import time

# 파일 구조 관리 및 디텍팅 

# =========================
# CONFIG
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_DIR = os.path.join(BASE_DIR, "input")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
ERROR_DIR = os.path.join(BASE_DIR, "error")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

def ensure_dirs() -> None:
    for d in [INPUT_DIR, PROCESSED_DIR, ERROR_DIR, OUTPUT_DIR]:
        os.makedirs(d, exist_ok=True)
        
def is_file_stable(path: str, stable_seconds: float = 0.6) -> bool:
    try:
        s1 = os.path.getsize(path)
        t1 = os.path.getmtime(path)
        time.sleep(stable_seconds)
        s2 = os.path.getsize(path)
        t2 = os.path.getmtime(path)
        return s1 == s2 and t1 == t2
    except FileNotFoundError:
        return False