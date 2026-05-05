import csv
import os
from typing import Dict, Any, Tuple, List, Optional
from app.services.helpers import (
    parse_sales,
    keyword_from_product_name,
)
from app.common.csv_utils import (
    _to_int,
    minmax_score_100,
    clamp_min,
    nz,
)
from app.services.helpers import (
    parse_sales,
    keyword_from_product_name,
)
from app.services.search_volume_service import (
    crawl_search_volume_dict_from_one_csv,
    resolve_search_value,
)
from app.loaders.csv_loader import (
    validate_csv,
    pick_col
)


# 이번주 파일에서 판매 순위를 읽기 위한 후보
RANK_COL_CANDIDATES = ["rank", "순위", "ranking"]

# 상품찜 컬럼 후보
LIKES_COL_CANDIDATES = ["likes", "찜", "찜하기", "찜하기수", "상품찜", "상품찜수"]

# 스토어찜 컬럼 후보
STORE_LIKES_COL_CANDIDATES = [
    "brand_likes",
    "brand_likesd",
    "스토어찜",
    "store_likes",
    "brand_like",
    "brand_likes_count",
]

# 검색량 컬럼 후보
NAVER_SEARCH_COL_CANDIDATES = [
    "naver_search",
    "검색량",
    "search_volume",
    "naver_volume",
    "검색수합계",
]

MIN_STORE_LIKES = 50
MIN_NAVER_SEARCH = 20

WEIGHTS = {
    "sales": 0.60,
    "likes_delta": 0.20,
    "store_search": 0.20,
}

def make_product_key(row: Dict[str, Any]) -> Tuple[str, str]:
    brand = (row.get("brand") or "").strip()
    product_name = (row.get("product_name") or "").strip()
    return brand, product_name

SNAPSHOT_LIKES_COL_CANDIDATES = ["likes", "찜", "상품찜", "상품찜수"]
SNAPSHOT_STORE_COL_CANDIDATES = ["store_likes", "brand_likes", "스토어찜", "brand_like"]
SNAPSHOT_SEARCH_COL_CANDIDATES = ["naver_search", "검색량", "search_volume", "검색수합계"]
SNAPSHOT_KEYWORD_COL_CANDIDATES = ["naver_keyword", "keyword", "검색키워드"]

def infer_platform_from_filename(filename: str) -> str:
    """
    파일명 기반으로 플랫폼 추론
    """
    s = filename.lower()

    if "musinsa" in s or "무신사" in s:
        return "MUSINSA"

    if "29cm" in s:
        return "29CM"

    if "wconcept" in s or "w_concept" in s or "w-concept" in s or "w컨셉" in s:
        return "WCONCEPT"

    if "coupang" in s or "쿠팡" in s:
        return "COUPANG"

    if "naver" in s or "스마트스토어" in s:
        return "NAVER"

    return "UNKNOWN"

def load_previous_snapshot_map(
    snapshot_path: Optional[str],
) -> Tuple[Dict[Tuple[str, str], Dict[str, Any]], List[str]]:
    """
    이전 snapshot CSV를 읽어 key=(brand, product_name) map 생성.
    snapshot이 없으면 빈 dict 반환.
    """
    warnings: List[str] = []

    if not snapshot_path:
        warnings.append("이전 snapshot이 없어 전체 상품을 신규로 처리함")
        return {}, warnings

    if not os.path.exists(snapshot_path):
        warnings.append(f"이전 snapshot 파일이 없어 전체 상품을 신규로 처리함: {snapshot_path}")
        return {}, warnings

    if not snapshot_path.lower().endswith(".csv"):
        raise ValueError(f"snapshot 파일이 CSV가 아님: {snapshot_path}")

    snapshot_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
    duplicate_count = 0

    with open(snapshot_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError(f"snapshot 헤더를 읽지 못함: {snapshot_path}")

        if "brand" not in reader.fieldnames or "product_name" not in reader.fieldnames:
            raise ValueError(
                f"snapshot 필수 컬럼 누락: brand, product_name / 현재: {reader.fieldnames}"
            )

        for row in reader:
            key = make_product_key(row)
            if not key[0] or not key[1]:
                continue

            if key in snapshot_map:
                duplicate_count += 1

            snapshot_map[key] = row

    if duplicate_count > 0:
        warnings.append(
            f"snapshot에서 중복 key(brand+product_name) {duplicate_count}건 발견: 마지막 행 기준 덮어씀"
        )

    return snapshot_map, warnings


def make_zero_previous_row(
    brand: str,
    product_name: str,
) -> Dict[str, Any]:
    return {
        "brand": brand,
        "product_name": product_name,
        "thumbnail": "",
        "likes": 0,
        "store_likes": 0,
        "naver_search": 0,
        "naver_keyword": keyword_from_product_name(product_name),
    }


def get_snapshot_value(
    row: Dict[str, Any],
    candidates: List[str],
) -> Optional[int]:
    col = pick_col(list(row.keys()), candidates)
    if not col:
        return None
    return parse_sales(row.get(col))


def get_snapshot_keyword(row: Dict[str, Any]) -> str:
    col = pick_col(list(row.keys()), SNAPSHOT_KEYWORD_COL_CANDIDATES)
    if col:
        return str(row.get(col) or "").strip()
    return keyword_from_product_name((row.get("product_name") or "").strip())


def resolve_current_search_value(
    row: Dict[str, Any],
    search_col: Optional[str],
    crawled_search_dict: Dict[str, int],
) -> Tuple[Optional[int], str, str]:
    """
    현재 CSV row의 검색량 결정.
    우선순위:
    1) 현재 CSV 컬럼값
    2) 현재 CSV product_name 기반 크롤링 dict
    """
    keyword = keyword_from_product_name((row.get("product_name") or "").strip())

    if search_col:
        raw = parse_sales(row.get(search_col))
        if raw is not None:
            return raw, "csv", keyword

    crawled = crawled_search_dict.get(keyword)
    if crawled is not None:
        return crawled, "crawl", keyword

    return None, "missing", keyword


def compute_ranking_from_csv_and_snapshot(
    current_csv_path: str,
    previous_snapshot_path: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, Any]]:
    warnings: List[str] = []

    ok, msg, fieldnames = validate_csv(current_csv_path)
    if not ok:
        raise ValueError(f"현재 CSV 검증 실패: {msg}")
    if not fieldnames:
        raise ValueError("현재 CSV 헤더 확인 실패")

    rank_col = pick_col(fieldnames, RANK_COL_CANDIDATES)
    likes_col = pick_col(fieldnames, LIKES_COL_CANDIDATES)
    store_col = pick_col(fieldnames, STORE_LIKES_COL_CANDIDATES)
    search_col = pick_col(fieldnames, NAVER_SEARCH_COL_CANDIDATES)

    if not rank_col:
        raise ValueError(f"현재 파일에 판매순위 컬럼이 필요함: candidates={RANK_COL_CANDIDATES}")
    if not likes_col:
        raise ValueError(f"현재 파일에 상품찜 컬럼이 필요함: candidates={LIKES_COL_CANDIDATES}")
    if not store_col:
        raise ValueError(f"현재 파일에 스토어찜 컬럼이 필요함: candidates={STORE_LIKES_COL_CANDIDATES}")

    if not search_col:
        warnings.append("현재 파일에 검색량 컬럼이 없어 크롤링 fallback 사용")

    previous_map, snapshot_warnings = load_previous_snapshot_map(previous_snapshot_path)
    warnings.extend(snapshot_warnings)

    crawled_search_dict, crawl_summary = crawl_search_volume_dict_from_one_csv(
        current_csv_path
    )

    if not search_col and crawl_summary.get("resolved_keywords", 0) == 0:
        warnings.append("현재 검색량 크롤링 결과가 0건임")

    rows: List[Dict[str, Any]] = []
    matched = 0
    new_items = 0
    duplicate_current_count = 0
    seen_current_keys = set()

    prev_search_from_snapshot = 0
    prev_search_missing = 0
    current_search_from_csv = 0
    current_search_from_crawl = 0
    current_search_missing = 0

    with open(current_csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            key = make_product_key(row)
            brand, product_name = key

            if not brand or not product_name:
                continue

            if key in seen_current_keys:
                duplicate_current_count += 1
            seen_current_keys.add(key)

            prev_row = previous_map.get(key)
            is_new_item = prev_row is None

            if is_new_item:
                new_items += 1
                prev_row = make_zero_previous_row(brand, product_name)

            matched += 1

            current_rank = _to_int(row.get(rank_col))

            current_likes = parse_sales(row.get(likes_col))
            prev_likes = get_snapshot_value(prev_row, SNAPSHOT_LIKES_COL_CANDIDATES)

            current_store = parse_sales(row.get(store_col))
            prev_store = get_snapshot_value(prev_row, SNAPSHOT_STORE_COL_CANDIDATES)

            prev_search = get_snapshot_value(prev_row, SNAPSHOT_SEARCH_COL_CANDIDATES)
            prev_keyword = get_snapshot_keyword(prev_row)

            if is_new_item:
                prev_search = 0
                prev_search_source = "new_item_zero"
            else:
                if prev_search is None:
                    prev_search = 0
                    prev_search_source = "snapshot_missing_zero"
                    prev_search_missing += 1
                else:
                    prev_search_source = "snapshot"
                    prev_search_from_snapshot += 1

            current_search, current_search_source, current_keyword = resolve_current_search_value(
                row,
                search_col,
                crawled_search_dict,
            )

            if current_search_source == "csv":
                current_search_from_csv += 1
            elif current_search_source == "crawl":
                current_search_from_crawl += 1
            elif current_search_source == "missing":
                current_search_missing += 1

            sales_score_raw = None
            if current_rank is not None:
                rr = 1 if current_rank < 1 else (100 if current_rank > 100 else current_rank)
                sales_score_raw = 101 - rr

            likes_delta_raw = None
            if current_likes is not None and prev_likes is not None:
                likes_delta_raw = current_likes - prev_likes

            store_delta_raw = None
            if current_store is not None and prev_store is not None:
                current_store_adj = clamp_min(current_store, MIN_STORE_LIKES)
                prev_store_adj = clamp_min(prev_store, MIN_STORE_LIKES)
                store_delta_raw = current_store_adj - prev_store_adj

            search_delta_raw = None
            if current_search is not None and prev_search is not None:
                current_search_adj = clamp_min(current_search, MIN_NAVER_SEARCH)
                prev_search_adj = clamp_min(prev_search, MIN_NAVER_SEARCH)
                search_delta_raw = current_search_adj - prev_search_adj

            rows.append({
                "platform": infer_platform_from_filename(os.path.basename(current_csv_path)),
                "brand": brand,
                "product_name": product_name,
                "thumbnail": (row.get("thumbnail") or "").strip(),

                "is_new_item": is_new_item,

                "this_month_rank": current_rank,

                "this_month_likes": current_likes,
                "last_month_likes": prev_likes,

                "this_month_store_likes": current_store,
                "last_month_store_likes": prev_store,

                "this_month_naver_search": current_search,
                "last_month_naver_search": prev_search,

                "this_month_naver_keyword": current_keyword,
                "last_month_naver_keyword": prev_keyword,

                "this_month_naver_source": current_search_source,
                "last_month_naver_source": prev_search_source,

                "sales_score_raw": sales_score_raw,
                "likes_delta_raw": likes_delta_raw,
                "store_delta_raw": store_delta_raw,
                "search_delta_raw": search_delta_raw,
            })

    if duplicate_current_count > 0:
        warnings.append(f"현재 파일에서 중복 key(brand+product_name) {duplicate_current_count}건 발견")

    if new_items > 0:
        warnings.append(f"신규 상품 {new_items}개는 지난달 값 0으로 처리하여 포함함")

    if matched == 0:
        raise ValueError("현재 CSV에서 계산 가능한 상품이 없음 (brand + product_name 기준)")

    if prev_search_missing > 0:
        warnings.append(f"snapshot에 지난달 검색량이 없는 상품 {prev_search_missing}건은 0으로 처리함")

    if current_search_from_crawl > 0:
        warnings.append(f"현재 검색량 {current_search_from_crawl}건은 크롤링 fallback 사용")
    if current_search_missing > 0:
        warnings.append(f"현재 검색량을 끝내 못 구한 상품 {current_search_missing}건 존재")

    likes_scores = minmax_score_100([x["likes_delta_raw"] for x in rows])
    store_scores = minmax_score_100([x["store_delta_raw"] for x in rows])
    search_scores = minmax_score_100([x["search_delta_raw"] for x in rows])

    for i, x in enumerate(rows):
        x["sales_score"] = float(x["sales_score_raw"]) if x["sales_score_raw"] is not None else None
        x["likes_score"] = likes_scores[i]
        x["store_score"] = store_scores[i]
        x["search_score"] = search_scores[i]

        valid_store_search = [v for v in [x["store_score"], x["search_score"]] if v is not None]
        x["store_search_score"] = (
            sum(valid_store_search) / len(valid_store_search)
            if valid_store_search else None
        )

        x["consumer_score"] = (
            nz(x["sales_score"]) * WEIGHTS["sales"]
            + nz(x["likes_score"]) * WEIGHTS["likes_delta"]
            + nz(x["store_search_score"]) * WEIGHTS["store_search"]
        )

    rows_sorted = sorted(rows, key=lambda r: r["consumer_score"], reverse=True)

    for rank, r in enumerate(rows_sorted, start=1):
        r["global_rank"] = rank

    meta = {
        "crawl_summary": crawl_summary,
        "matched_count": matched,
        "new_items_included_with_zero_last_month": new_items,
        "prev_search_from_snapshot": prev_search_from_snapshot,
        "prev_search_missing_zero": prev_search_missing,
        "current_search_from_csv": current_search_from_csv,
        "current_search_from_crawl": current_search_from_crawl,
        "current_search_missing": current_search_missing,
        "previous_snapshot_path": previous_snapshot_path,
    }

    return rows_sorted, warnings, meta