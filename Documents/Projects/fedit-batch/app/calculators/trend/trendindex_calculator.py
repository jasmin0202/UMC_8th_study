import sys
import json
import pandas as pd
import numpy as np
from typing import Any, Dict, List

from app.services.helpers import min_max_0_100


def _build_dataframe(products: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(products)

    df.rename(
        columns={
            "detail_category": "category",
            "reviews": "review",
            "detail_category_top_frequency": "top_frequency",
            "brand_search_volume": "brand_volume",
            "brand_category_volume": "category_volume",
        },
        inplace=True,
    )

    num_cols = [
        "insta",
        "brand_volume",
        "category_volume",
        "top_frequency",
        "review",
        "sales",
        "days_since_registered",
    ]

    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).clip(lower=0)

    return df


def calculate_from_products(products: List[Dict[str, Any]]) -> pd.DataFrame:
    df = _build_dataframe(products)

    if df.empty:
        return df

    required_defaults = {
        "insta": 0,
        "brand_volume": 0,
        "category_volume": 0,
        "top_frequency": 0,
        "review": 0,
        "sales": 0,
        "days_since_registered": 0,
    }
    for col, default_value in required_defaults.items():
        if col not in df.columns:
            df[col] = default_value

    # 1) 브랜드지수
    insta = df["insta"]
    brand_volume = df["brand_volume"]

    if insta.max() > 0:
        insta_score = np.log10(insta + 1) / np.log10(insta.max() + 1) * 50
    else:
        insta_score = 0

    if brand_volume.max() > 0:
        brand_volume_score = np.log10(brand_volume + 1) / np.log10(brand_volume.max() + 1) * 50
    else:
        brand_volume_score = 0

    df["brand_index"] = np.round(insta_score + brand_volume_score, 2)

    # 2) 유형지수
    category_volume = df["category_volume"]
    top_frequency = df["top_frequency"]

    if category_volume.max() > 0:
        category_volume_score = np.log10(category_volume + 1) / np.log10(category_volume.max() + 1) * 60
    else:
        category_volume_score = 0

    if top_frequency.max() > 0:
        top_frequency_score = top_frequency / top_frequency.max() * 40
    else:
        top_frequency_score = 0

    df["type_index"] = np.round(category_volume_score + top_frequency_score, 2)

    # 3) 구매전환률
    review = df["review"]
    sales = df["sales"]
    age = df["days_since_registered"]

    review_adjusted = review / np.sqrt(age + 1)
    base = sales * np.sqrt(age + 1) / review.replace(0, np.nan)

    weight = np.where(
        review_adjusted < 5,
        review_adjusted / 5,
        np.where(
            review_adjusted < 20,
            0.6 + (review_adjusted - 5) / 15 * 0.4,
            1.0,
        ),
    )

    df["review_adjusted"] = np.round(review_adjusted, 4)
    df["conversion_weight"] = np.round(np.nan_to_num(weight, nan=0.0), 4)
    df["conversion_rate"] = np.round(
        (base * df["conversion_weight"]).fillna(0),
        4
    )

    # 4) 정규화
    df["brand_score"] = min_max_0_100(df["brand_index"]).round(2)
    df["category_score"] = min_max_0_100(df["type_index"]).round(2)
    df["purchase_score"] = min_max_0_100(df["conversion_rate"]).round(2)

    # 5) 최종 소비자 지수
    df["consumer_score"] = (
        df["brand_score"] * 0.33
        + df["category_score"] * 0.33
        + df["purchase_score"] * 0.34
    ).round(2)

    # 6) 최종 출력용 컬럼 구성
    # search는 상품 단위 검색 수요로 보기 위해 category_volume 사용
    df["search"] = df["category_volume"]
    df["sales_count"] = df["sales"]

    # 7) 정렬 + rank
    df = df.sort_values(
        by=["consumer_score", "sales_count", "search"],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    df["rank"] = np.arange(1, len(df) + 1)

    return df


def get_final_output_columns(df: pd.DataFrame) -> List[str]:
    """
    사용자가 원하는 최종 CSV 컬럼 순서
    csv 기본정보 + search + purchase_score + sales_count + category_score + rank + consumer_score
    """
    preferred_cols = [
        # csv 기본정보
        "product_name",
        "brand",
        "category",
        "manufactured_date",
        "days_since_registered",
        "review",
        "rating",

        # 계산/보강 컬럼
        "search",
        "purchase_score",
        "sales_count",
        "category_score",
        "rank",
        "consumer_score",
    ]
    return [c for c in preferred_cols if c in df.columns]


def write_result_csv(df: pd.DataFrame, output_csv: str) -> None:
    output_cols = get_final_output_columns(df)
    df[output_cols].to_csv(output_csv, index=False, encoding="utf-8-sig")


def run_from_products(products: List[Dict[str, Any]], output_csv: str = "output.csv") -> pd.DataFrame:
    df = calculate_from_products(products)
    write_result_csv(df, output_csv)
    print(f"🎯 분석 완료! 결과 → {output_csv}")
    return df


def main(input_json: str, output_csv: str = "output.csv"):
    with open(input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    run_from_products(data, output_csv)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trendIndex_calculator.py input.json [output.csv]")
        sys.exit(1)

    input_json = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) >= 3 else "output.csv"
    main(input_json, output_csv)