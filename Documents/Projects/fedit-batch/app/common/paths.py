import json
import os
import re
from typing import Dict, Any, List, Optional

import pandas as pd


# --------------------------------------------------
# 유틸
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