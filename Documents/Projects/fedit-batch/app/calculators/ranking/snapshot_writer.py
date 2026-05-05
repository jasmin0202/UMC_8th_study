# app/calculators/ranking/snapshot_writer.py
# -*- coding: utf-8 -*-

import csv
import os
from typing import Dict, Any, List


SNAPSHOT_COLS = [
    "platform",
    "brand",
    "product_name",
    "thumbnail",
    "likes",
    "store_likes",
    "naver_search",
    "naver_keyword",
]


def make_snapshot_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    ranking 계산 결과 rows를 다음 회차 비교용 snapshot row 형태로 변환.
    """
    snapshot_rows: List[Dict[str, Any]] = []

    for r in rows:
        snapshot_rows.append({
            "platform": r.get("platform"),
            "brand": r.get("brand"),
            "product_name": r.get("product_name"),
            "thumbnail": r.get("thumbnail"),
            "likes": r.get("this_month_likes"),
            "store_likes": r.get("this_month_store_likes"),
            "naver_search": r.get("this_month_naver_search"),
            "naver_keyword": r.get("this_month_naver_keyword"),
        })

    return snapshot_rows


def write_snapshot_csv(out_path: str, rows: List[Dict[str, Any]]) -> None:
    """
    ranking 결과 rows를 snapshot CSV로 저장.
    """
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    snapshot_rows = make_snapshot_rows(rows)

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SNAPSHOT_COLS)
        writer.writeheader()
        for row in snapshot_rows:
            writer.writerow({k: row.get(k) for k in SNAPSHOT_COLS})