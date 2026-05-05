import os
from typing import Any, Dict, List
import json
import csv

# 랭킹 계산 결과 CSV 및 메타 JSON 작성 (수정 필요)

def write_ranking_csv(out_path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    cols = [
        "global_rank",
        "platform",
        "consumer_score",
        "is_new_item",

        "brand",
        "product_name",
        "thumbnail",

        "this_week_rank",

        "this_week_likes",
        "last_week_likes",

        "this_week_store_likes",
        "last_week_store_likes",

        "this_week_naver_search",
        "last_week_naver_search",

        "this_week_naver_keyword",
        "last_week_naver_keyword",

        "this_week_naver_source",
        "last_week_naver_source",

        "sales_score_raw",
        "likes_delta_raw",
        "store_delta_raw",
        "search_delta_raw",

        "sales_score",
        "likes_score",
        "store_score",
        "search_score",
        "store_search_score",
    ]

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in cols})

def write_meta_json(out_path: str, meta: Dict[str, Any], warnings: List[str]) -> None:
    payload = {
        "meta": meta,
        "warnings": warnings,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
