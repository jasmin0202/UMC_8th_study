import csv
import json
import os
import time
import shutil
from typing import Dict, Any, Optional, Tuple, List

REQUIRED_COLUMNS = ["thumbnail", "product_name", "brand"]


# csv 유효성 검증 

def validate_csv(path: str) -> Tuple[bool, str, Optional[List[str]]]:
    if not path.lower().endswith(".csv"):
        return False, "확장자가 .csv가 아님", None
    if not os.path.exists(path):
        return False, "파일이 존재하지 않음", None

    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return False, "헤더를 읽지 못함", None

            missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
            if missing:
                return False, f"필수 컬럼 누락: {missing} / 현재: {reader.fieldnames}", reader.fieldnames

            return True, "OK", reader.fieldnames
    except Exception as e:
        return False, f"CSV 파싱 실패: {e}", None
    
def pick_col(fieldnames: List[str], candidates: List[str]) -> Optional[str]:
    s = set(fieldnames or [])
    for c in candidates:
        if c in s:
            return c
    return None