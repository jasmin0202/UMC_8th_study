
# -*- coding: utf-8 -*-
# dict를 만들고, csv를 기반으로 run_trendindex_job에서 사용할 json파일을 생성하는 스크립트
import csv
import json
import os
import re
import time
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.helpers import fetch_ma_pia_volumes, MAX_PER_RUN
from app.calculators.trend.dicts.dicts import brand_instagram_volume_dict, detail_category_top_frequency_dict

# -------------------------
# 기본 유틸
# -------------------------
def normalize_key(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = re.sub(r"\s+", "", s)
    return s


def normalize_volume(value: Optional[int]) -> int:
    """검색량이 None/0 이하이면 1로 보정"""
    if value is None:
        return 1
    try:
        v = int(value)
    except (TypeError, ValueError):
        return 1
    return 1 if v <= 0 else v


def simplify_category(category_raw: str) -> str:
    if not category_raw:
        return ""
    s = str(category_raw).strip()
    if "/" in s:
        return s.split("/")[0].strip()
    return s


def parse_manufacture_date(date_str: str) -> str:
    if not date_str:
        return ""

    s = str(date_str).strip().replace(" ", "").replace("/", "-")

    kor = re.search(r"(\d{2,4})년(\d{1,2})월", s)
    if kor:
        y, m = kor.groups()
        yy = int(y)
        mm = int(m)
        if yy < 100:
            yy += 2000
        return f"{yy:04d}-{mm:02d}-01"

    if s.isdigit() and len(s) == 8:  # YYYYMMDD
        yy = int(s[:4])
        mm = int(s[4:6])
        dd = int(s[6:8])
        return f"{yy:04d}-{mm:02d}-{dd:02d}"

    if s.isdigit() and len(s) == 6:  # YYYYMM
        yy = int(s[:4])
        mm = int(s[4:6])
        return f"{yy:04d}-{mm:02d}-01"

    if "." in s:
        parts = [p for p in s.split(".") if p]
        if len(parts) == 2:
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}-01"
        if len(parts) == 3:
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"

    parts = [p for p in s.split("-") if p]
    if len(parts) == 3:
        try:
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        except ValueError:
            return ""

    return ""


def calc_days_since(date_str: str) -> int:
    if not date_str:
        return 0
    try:
        y, m, d = map(int, date_str.split("-"))
        dt = date(y, m, d)
        return (date.today() - dt).days
    except Exception:
        return 0


def parse_sales(sales_str: Any) -> int:
    if sales_str is None:
        return 0

    s = str(sales_str).strip().replace(" ", "").replace(",", "")
    s = s.replace("개", "")

    if s in ("", "-"):
        return 0
    if re.fullmatch(r"\d+", s):
        return int(s)

    if s.endswith("천"):
        try:
            return int(float(s[:-1]) * 1000)
        except ValueError:
            return 0

    if s.endswith("만"):
        try:
            return int(float(s[:-1]) * 10000)
        except ValueError:
            return 0

    return 0


def parse_rating(x: Any) -> float:
    if x is None:
        return 0.0
    s = str(x).strip()
    if s in ("", "-"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _chunk(lst: List[str], n: int) -> List[List[str]]:
    return [lst[i:i + n] for i in range(0, len(lst), n)]


def _load_ckpt(path: Optional[str]) -> Dict[str, int]:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {str(k): int(v) for k, v in data.items()}


def _save_ckpt(path: Optional[str], data: Dict[str, int]) -> None:
    if not path:
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# -------------------------
# CSV 스캔
# -------------------------
def scan_csv_once(csv_path: str) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """
    CSV를 1회 스캔해서
    1) row 정규화 목록
    2) 유니크 브랜드 키 목록
    3) 유니크 brand+detail 키 목록
    반환
    """
    rows: List[Dict[str, Any]] = []
    brands: Set[str] = set()
    brand_detail_keys: Set[str] = set()

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for r in reader:
            product_name = (r.get("product_name") or "").strip()
            brand_raw = (r.get("brand") or "").strip()
            category_raw = (r.get("category") or "").strip()
            detail_category_raw = (r.get("detail_category") or "").strip()

            if not brand_raw:
                continue

            brand_key = normalize_key(brand_raw)
            brands.add(brand_key)

            category_simple = simplify_category(category_raw)
            detail_simple = simplify_category(detail_category_raw)
            detail_key = normalize_key(detail_simple) if detail_simple else ""

            if detail_key:
                brand_detail_keys.add(f"{brand_key}{detail_key}")

            rows.append({
                "product_name": product_name,
                "brand_raw": brand_raw,
                "brand_key": brand_key,
                "category": category_simple,
                "detail_category": detail_simple,
                "detail_key": detail_key,
                "manufacture_date_raw": (r.get("manufacture_date") or "").strip(),
                "sales_raw": (r.get("sales") or "").strip(),
                "reviews_raw": (r.get("reviews") or "").strip(),
                "rating_raw": r.get("rating"),
            })

    return rows, sorted(brands), sorted(brand_detail_keys)


# -------------------------
# 마피아넷 검색량 조회
# -------------------------
def build_keyword_volume_dict(
    keywords: List[str],
    *,
    checkpoint_path: Optional[str],
    sleep_between_batches: float = 1.2,
    label: str = "keywords",
) -> Dict[str, int]:
    """
    keyword 목록에 대해 검색량 dict 생성.
    checkpoint를 사용해 이미 처리한 키워드는 재조회하지 않음.
    """
    results = _load_ckpt(checkpoint_path)
    done = set(results.keys())
    todo = [k for k in keywords if k not in done]

    total = len(keywords)
    done_n = len(done)
    todo_n = len(todo)

    print(f"[{label}] total={total} done={done_n} remaining={todo_n} ckpt={checkpoint_path}")

    processed = 0
    started = time.time()

    for batch_i, group in enumerate(_chunk(todo, MAX_PER_RUN), start=1):
        safe: List[str] = []
        blocked: List[str] = []

        for k in group:
            if any(bad in k for bad in ["'", '"', "\\", ","]):
                blocked.append(k)
            else:
                safe.append(k)

        for k in blocked:
            results[k] = results.get(k, 0)

        if safe:
            df = fetch_ma_pia_volumes(
                safe,
                include_blog_info=False,
                sleep_between_batches=0.0,
                output="df",
            )
            got = {row["키워드"]: int(row["검색수합계"]) for _, row in df.iterrows()} if not df.empty else {}

            for k in safe:
                results[k] = int(got.get(k, 0))

        _save_ckpt(checkpoint_path, results)

        processed += len(group)
        elapsed = time.time() - started
        remaining = max(todo_n - processed, 0)
        rate = processed / elapsed if elapsed > 0 else 0
        eta = remaining / rate if rate > 0 else 0

        print(
            f"[{label}] batch {batch_i} "
            f"+{len(group)} (safe={len(safe)}, blocked={len(blocked)}) "
            f"progress {processed}/{todo_n} "
            f"elapsed={elapsed:.1f}s eta={eta:.1f}s"
        )

        time.sleep(sleep_between_batches)

    return results


# -------------------------
# products 생성
# -------------------------
def build_products_json_object(
    csv_path: str,
    *,
    brand_instagram_volume_dict: Dict[str, int],
    detail_category_top_frequency_dict: Dict[str, int],
    ckpt_brand: str = "ckpt_brand_volume.json",
    ckpt_brand_detail: str = "ckpt_brand_detail_volume.json",
) -> List[Dict[str, Any]]:
    rows, brands, brand_detail_keys = scan_csv_once(csv_path)

    brand_search_volume_dict = build_keyword_volume_dict(
        brands,
        checkpoint_path=ckpt_brand,
        label="brand",
    )

    brand_category_volume_dict = build_keyword_volume_dict(
        brand_detail_keys,
        checkpoint_path=ckpt_brand_detail,
        label="brand_detail",
    )

    insta_norm = {normalize_key(k): int(v) for k, v in brand_instagram_volume_dict.items()}

    products: List[Dict[str, Any]] = []

    for r in rows:
        brand_key = r["brand_key"]
        detail_key = r["detail_key"]
        
        brand_volume = normalize_volume(
            brand_search_volume_dict.get(brand_key.upper())
        )

        raw_brand_detail = None
        if detail_key:
            # 띄어쓰기 없이 붙여서 대문자로 조회 (마피아넷 응답 기준)
            lookup_key = f"{brand_key}{detail_key}".upper().replace(" ", "")
            raw_brand_detail = brand_category_volume_dict.get(lookup_key)

        brand_category_volume = normalize_volume(raw_brand_detail)
        insta_followers = int(insta_norm.get(brand_key, 0))

        manufactured_date = parse_manufacture_date(r["manufacture_date_raw"])
        days_since_registered = calc_days_since(manufactured_date)

        sales = parse_sales(r["sales_raw"])
        if sales == 0:
            reviews_count = parse_sales(r["reviews_raw"])
            if reviews_count > 0:
                sales = reviews_count * 5
            else:
                sales = 1

        rating = parse_rating(r["rating_raw"])
        detail_freq = int(detail_category_top_frequency_dict.get(r["detail_category"], 0))

        products.append({
            "product_name": r["product_name"],
            "detail_category": r["detail_category"],
            "brand": r["brand_raw"],
            "manufactured_date": manufactured_date,
            "days_since_registered": days_since_registered,
            "insta": insta_followers,
            "brand_search_volume": brand_volume,
            "brand_category_volume": brand_category_volume,
            "detail_category_top_frequency": detail_freq,
            "reviews": r["reviews_raw"],
            "sales": sales,
            "rating": rating,
            "category": r["category"],
        })

    return products


def save_products_json(csv_path: str, out_json_path: str, **kwargs) -> str:
    obj = build_products_json_object(csv_path, **kwargs)
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return out_json_path


# -------------------------
# CLI
# -------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build Musinsa Kids JSON with MafiaNet volumes.")
    parser.add_argument("--csv", required=True, help="input csv path")
    parser.add_argument("--out", default="musinsa_out.json", help="output json path")
    parser.add_argument("--ckpt_brand", default="ckpt_brand_volume.json")
    parser.add_argument("--ckpt_brand_detail", default="ckpt_brand_detail_volume.json")
    parser.add_argument("--preview", type=int, default=5, help="preview N items from JSON")
    args = parser.parse_args()

    try:
        brand_instagram_volume_dict
    except NameError:
        brand_instagram_volume_dict = {}

    try:
        detail_category_top_frequency_dict
    except NameError:
        detail_category_top_frequency_dict = {}

    rows, brands, brand_detail_keys = scan_csv_once(args.csv)
    print(f"[scan] rows={len(rows)} brands={len(brands)} brand_detail_keys={len(brand_detail_keys)}")

    products = build_products_json_object(
        args.csv,
        brand_instagram_volume_dict=brand_instagram_volume_dict,
        detail_category_top_frequency_dict=detail_category_top_frequency_dict,
        ckpt_brand=args.ckpt_brand,
        ckpt_brand_detail=args.ckpt_brand_detail,
    )

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(f"[ok] saved json: {args.out} (items={len(products)})")

    n = max(0, args.preview)
    if n > 0:
        print(f"\n[preview top {n}]")
        for i, p in enumerate(products[:n], start=1):
            print(
                f"{i}. brand={p.get('brand')} "
                f"detail_category={p.get('detail_category')} "
                f"insta={p.get('insta')} "
                f"brand_search_volume={p.get('brand_search_volume')} "
                f"brand_category_volume={p.get('brand_category_volume')} "
                f"sales={p.get('sales')} reviews={p.get('reviews')} "
                f"date={p.get('manufactured_date')}"
            )