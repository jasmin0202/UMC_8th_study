from typing import Dict, Any, Optional, Tuple, List

from .helpers import (
    parse_sales,
    fetch_ma_pia_volumes,
    build_keywords_from_csv,
    keyword_from_product_name,
)

from app.common.csv_utils import _to_int


def crawl_search_volume_dict_from_one_csv(
    csv_path: str,
) -> Tuple[Dict[str, int], Dict[str, Any]]:
    """
    현재 CSV 하나에서 product_name 키워드를 뽑아 검색량 조회.
    """
    targets = build_keywords_from_csv(csv_path, name_col="product_name")

    if not targets:
        return {}, {
            "queried_keywords": 0,
            "resolved_keywords": 0,
            "error": None,
        }

    df = fetch_ma_pia_volumes(
        sorted(set(targets)),
        include_blog_info=False,
        sleep_between_batches=1.0,
        output="df",
    )

    search_dict: Dict[str, int] = {}
    if df is not None and not df.empty:
        for _, r in df.iterrows():
            kw = str(r.get("키워드") or "").strip()
            total = _to_int(r.get("검색수합계"))
            if kw and total is not None:
                search_dict[kw] = total

    return search_dict, {
        "queried_keywords": len(set(targets)),
        "resolved_keywords": len(search_dict),
        "error": None,
    }
    
def resolve_search_value(
    row: Dict[str, Any],
    search_col: Optional[str],
    crawled_search_dict: Dict[str, int],
) -> Tuple[Optional[int], str, str]:
    """
    우선순위:
    1) CSV 컬럼에 검색량 값이 있으면 그 값 사용
    2) 없으면 product_name -> keyword 변환 후 크롤링 dict 사용
    반환:
      (search_value, source, keyword)
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

