import pandas as pd
import numpy as np
from pathlib import Path


def add_unique_rank(
    input_path="trend_index.csv",
    output_path="output_enriched.csv",
    brand_col="brand",
    type_col="category", 
    brand_score_col="brand_score",
    type_score_col="type_score",
    brand_agg="max",
    type_agg="max",
    rank_method="average",
):
    df = pd.read_csv(input_path)

    # 숫자 변환
    for c in [brand_score_col, type_score_col]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # ---------------------------
    # 1️⃣ BRAND (유니크 브랜드 기준)
    # ---------------------------
    brand_tbl = (
        df.groupby(brand_col)[brand_score_col]
        .agg(brand_agg)
        .reset_index()
        .rename(columns={brand_score_col: "brand_rep_score"})
    )

    brand_tbl["brand_percentile"] = (
        brand_tbl["brand_rep_score"].rank(pct=True, method=rank_method) * 100
    )
    brand_tbl["brand_top_pct"] = 100 - brand_tbl["brand_percentile"]

    df = df.merge(brand_tbl, on=brand_col, how="left")

    # ---------------------------
    # 2️⃣ TYPE (유니크 타입 기준)
    # ---------------------------
    type_tbl = (
        df.groupby(type_col)[type_score_col]
        .agg(type_agg)
        .reset_index()
        .rename(columns={type_score_col: "type_rep_score"})
    )

    type_tbl["type_percentile"] = (
        type_tbl["type_rep_score"].rank(pct=True, method=rank_method) * 100
    )
    type_tbl["type_top_pct"] = 100 - type_tbl["type_percentile"]

    df = df.merge(type_tbl, on=type_col, how="left")

    # 반올림
    for col in ["brand_percentile", "brand_top_pct",
                "type_percentile", "type_top_pct"]:
        df[col] = df[col].round(4)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


if __name__ == "__main__":
    print(add_unique_rank())