# app/jobs/run_ranking_job.py
# -*- coding: utf-8 -*-

import json
import os
import re
from typing import Optional, Dict, Any, List

import pandas as pd

from app.calculators.ranking.ranking_calculator import (
    compute_ranking_from_csv_and_snapshot,
)
from app.calculators.ranking.ranking_writer import (
    write_ranking_csv,
    write_meta_json,
)
from app.calculators.ranking.snapshot_writer import (
    write_snapshot_csv,
)


# --------------------------------------------------
# 후처리 유틸
# --------------------------------------------------
def normalize_platform(value: str) -> str:
    if value is None:
        return "unknown"
    return str(value).strip().lower()


def safe_filename(value: str) -> str:
    if value is None:
        return "unknown"
    s = str(value).strip()
    s = s.replace("/", "_")
    s = re.sub(r'[\\:*?"<>|]', "_", s)
    s = re.sub(r"\s+", "_", s)
    return s


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# --------------------------------------------------
# 2) 랭킹 JSON 1개 생성
# --------------------------------------------------
def build_ranking_json(
    df: pd.DataFrame,
    platform: str,
    category: str,
    date_str: str,
    top_n: int = 30,
) -> Dict[str, Any]:
    """
    merge된 DataFrame을 받아 상위 N개를 랭킹 JSON으로 변환.
    정렬 기준:
      1) consumer_score desc
      2) global_rank asc
    """
    if df.empty:
        top_df = df.copy()
    else:
        sort_cols = []
        ascending = []

        if "consumer_score" in df.columns:
            sort_cols.append("consumer_score")
            ascending.append(False)

        if "global_rank" in df.columns:
            sort_cols.append("global_rank")
            ascending.append(True)

        if sort_cols:
            top_df = (
                df.sort_values(by=sort_cols, ascending=ascending)
                .head(top_n)
                .reset_index(drop=True)
            )
        else:
            top_df = df.head(top_n).reset_index(drop=True)

    result: List[Dict[str, Any]] = []

    for i, row in top_df.iterrows():
        result.append({
            "product_name": row.get("product_name"),
            "thumbnail": row.get("thumbnail"),
            "brand": row.get("brand"),
            "rank": i + 1,
            "itemcode": row.get("itemcode"),
        })

    return {
        "platform": normalize_platform(platform),
        "category": category,
        "date": date_str,
        "rankData": {
            "result": result
        }
    }


# --------------------------------------------------
# 3) all + category별 JSON 여러 개 생성
# --------------------------------------------------
def build_all_ranking_jsons(
    df: pd.DataFrame,
    platform: str,
    date_str: str,
    category_col: str = "category",
    top_n: int = 30,
    fixed_categories: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    if fixed_categories is None:
        fixed_categories = ["상의", "바지", "아우터", "원피스/스커트"]

    outputs: List[Dict[str, Any]] = []

    # all
    outputs.append(
        build_ranking_json(
            df=df,
            platform=platform,
            category="all",
            date_str=date_str,
            top_n=top_n,
        )
    )

    # category별
    for cat in fixed_categories:
        if category_col in df.columns:
            sub_df = df[df[category_col] == cat].copy()
        else:
            sub_df = pd.DataFrame(columns=df.columns)

        outputs.append(
            build_ranking_json(
                df=sub_df,
                platform=platform,
                category=cat,
                date_str=date_str,
                top_n=top_n,
            )
        )

    return outputs


# --------------------------------------------------
# 4) score 포함 CSV 저장
# --------------------------------------------------
def write_scored_csv(
    original_df: pd.DataFrame,
    ranking_df: pd.DataFrame,
    output_csv_path: str,
    *,
    join_keys: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    원본 상품 CSV + 최종 랭킹 CSV를 merge한 뒤
    DB 적재용 점수 컬럼을 추가해서 저장.

    새 랭킹 CSV 기준 매핑:
      brandScore    <- likes_score
      search        <- this_week_naver_search
      marketScore   <- store_search_score
      purchaseScore <- sales_score
      categoryScore <- consumer_score
    """
    if join_keys is None:
        join_keys = ["brand", "product_name"]

    score_df = ranking_df.copy()

    needed_cols = [c for c in [
        *join_keys,
        "global_rank",
        "consumer_score",
        "this_week_naver_search",
        "sales_score",
        "likes_score",
        "store_search_score",
        "this_week_rank",
        "is_new_item",
    ] if c in score_df.columns]

    score_df = score_df[needed_cols].copy()

    rename_map = {
        "likes_score": "brandScore",
        "this_week_naver_search": "search",
        "store_search_score": "marketScore",
        "sales_score": "purchaseScore",
        "consumer_score": "categoryScore",
    }
    score_df.rename(columns=rename_map, inplace=True)

    merged = original_df.merge(score_df, on=join_keys, how="left")

    ensure_dir(os.path.dirname(output_csv_path) or ".")
    merged.to_csv(output_csv_path, index=False, encoding="utf-8-sig")

    return merged


# --------------------------------------------------
# 5) JSON 파일들 저장
# --------------------------------------------------
def write_ranking_json_files(
    ranking_jsons: List[Dict[str, Any]],
    output_dir: str,
) -> List[str]:
    ensure_dir(output_dir)

    saved_paths: List[str] = []

    for payload in ranking_jsons:
        platform = safe_filename(payload.get("platform", "unknown"))
        category = safe_filename(payload.get("category", "all"))
        date_str = safe_filename(payload.get("date", "unknown"))

        file_name = f"{platform}_{category}_{date_str}_ranking.json"
        out_path = os.path.join(output_dir, file_name)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        saved_paths.append(out_path)

    return saved_paths


# --------------------------------------------------
# 메인 job
# --------------------------------------------------
def run_ranking_job(
    current_csv_path: str,
    output_dir: str,
    previous_snapshot_path: Optional[str] = None,
    date_str: str = "2026-03-w01", # 이거 파일명에서 가져오게 수정
) -> Dict[str, Any]:
    """
    현재 CSV + 이전 snapshot 으로 ranking 계산 후

    1) ranking csv 저장
    2) meta json 저장
    3) 다음 회차용 snapshot csv 저장
    4) 원본 상품 csv + score merge 후 scored csv 저장
    5) all + category별 ranking json 저장
    """
    os.makedirs(output_dir, exist_ok=True)

    rows, warnings, meta = compute_ranking_from_csv_and_snapshot(
        current_csv_path=current_csv_path,
        previous_snapshot_path=previous_snapshot_path,
    )

    current_base = os.path.splitext(os.path.basename(current_csv_path))[0]

    ranking_csv_path = os.path.join(output_dir, f"{current_base}_ranking.csv")
    meta_json_path = os.path.join(output_dir, f"{current_base}_ranking_meta.json")
    snapshot_csv_path = os.path.join(output_dir, f"{current_base}_snapshot.csv")
    scored_csv_path = os.path.join(output_dir, f"{current_base}_scored.csv")
    ranking_json_dir = os.path.join(output_dir, f"{current_base}_ranking_jsons")

    # 기존 산출물 저장
    write_ranking_csv(ranking_csv_path, rows)
    write_meta_json(meta_json_path, meta, warnings)
    write_snapshot_csv(snapshot_csv_path, rows)

    # 메모리 rows -> ranking_df
    ranking_df = pd.DataFrame(rows)

    # 원본 상품 CSV 로드
    original_df = pd.read_csv(current_csv_path, encoding="utf-8-sig")

    # score 포함 CSV 생성
    scored_df = write_scored_csv(
        original_df=original_df,
        ranking_df=ranking_df,
        output_csv_path=scored_csv_path,
        join_keys=["brand", "product_name"],
    )

    # platform 결정: ranking 결과에 있으면 그 값 사용
    if not ranking_df.empty and "platform" in ranking_df.columns:
        platform = str(ranking_df["platform"].iloc[0])
    else:
        platform = "unknown"

    # all + category별 ranking json 생성
    ranking_jsons = build_all_ranking_jsons(
        df=scored_df,
        platform=platform,
        date_str=date_str,
        category_col="category",
        top_n=30,
    )

    ranking_json_paths = write_ranking_json_files(
        ranking_jsons=ranking_jsons,
        output_dir=ranking_json_dir,
    )

    return {
        "job_type": "ranking",
        "input_csv": current_csv_path,
        "previous_snapshot_path": previous_snapshot_path,
        "rows_scored": len(rows),
        "warnings": warnings,
        "meta": meta,
        "artifacts": {
            "ranking_csv": ranking_csv_path,
            "meta_json": meta_json_path,
            "snapshot_csv": snapshot_csv_path,
            "scored_csv": scored_csv_path,
            "ranking_json_dir": ranking_json_dir,
            "ranking_json_files": ranking_json_paths,
        },
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run ranking job from current CSV + previous snapshot")
    parser.add_argument("--current_csv_path", required=True, help="현재 월 CSV 경로")
    parser.add_argument("--output_dir", default="output", help="결과 저장 디렉토리")
    parser.add_argument("--previous_snapshot_path", default=None, help="이전 snapshot CSV 경로")
    parser.add_argument("--date_str", default="2026-03-w01", help="랭킹 JSON에 들어갈 날짜 문자열")

    args = parser.parse_args()

    result = run_ranking_job(
        current_csv_path=args.current_csv_path,
        output_dir=args.output_dir,
        previous_snapshot_path=args.previous_snapshot_path,
        date_str=args.date_str,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))