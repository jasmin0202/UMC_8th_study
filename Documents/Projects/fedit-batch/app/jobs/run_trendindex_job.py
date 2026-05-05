import argparse
import os
import csv
import json
from pathlib import Path

# 기존 임포트
from app.calculators.trend.json_builder import save_products_json
from app.calculators.trend.trendindex_calculator import main as run_from_products
from app.calculators.trend.dicts.dicts import (
    brand_instagram_volume_dict,
    detail_category_top_frequency_dict,
)

# --- 병합 함수 추가 ---
def merge_and_save_final_json(original_json_path, csv_result_path, final_output_path):
    """원본 JSON과 트렌드 CSV 결과를 합쳐서 최종 JSON 생성"""
    if not os.path.exists(original_json_path):
        print(f"⚠️ 원본 JSON을 찾을 수 없어 병합을 건너뜁니다: {original_json_path}")
        return

    # 1. 원본 JSON 로드
    with open(original_json_path, 'r', encoding='utf-8') as f:
        original_data = json.load(f)

    # 2. 결과 CSV 로드 (상품명을 키로 매핑)
    trend_results = {}
    with open(csv_result_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trend_results[row['product_name']] = row

    # 3. 데이터 매칭 및 주입
    final_output = []
    for item in original_data:
        name = item.get('product_name')
        if name in trend_results:
            res = trend_results[name]
            # CSV 값을 JSON 형식에 맞춰 업데이트 (원하는 필드명으로 매핑)
            item.update({
                "search": int(float(res.get('search', 0))),
                "purchase_score": float(res.get('purchase_score', 0)),
                "category_score": float(res.get('category_score', 0)),
                "market_score": float(res.get('consumer_score', 0)),  # consumer -> market
                "rank": int(res.get('rank', 0)),
                "brand_score": 0.0, # 필요시 로직 추가
                "is_platform": False
            })
        final_output.append(item)

    # 4. 최종 JSON 저장
    with open(final_output_path, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    print(f"✨ 최종 결과물 생성 완료: {final_output_path}")


def run_trendindex_job(
    input_csv: str,
    out_dir: str,
    *,
    json_name: str = "products.json",
    result_csv_name: str = "trend_index.csv",
    ckpt_brand: str = "ckpt_brand_volume.json",
    ckpt_brand_detail: str = "ckpt_brand_detail_volume.json",
    original_json_path: str = None, # 원본 JSON 경로 인자 추가
):
    out_dir_p = Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)

    out_json = str(out_dir_p / json_name)
    out_csv = str(out_dir_p / result_csv_name)
    final_json = str(out_dir_p / "final_trend_result.json") # 최종 파일명

    ckpt_brand_path = str(out_dir_p / ckpt_brand)
    ckpt_brand_detail_path = str(out_dir_p / ckpt_brand_detail)

    print("=== PIPELINE START ===")
    # 1) JSON 생성 (내부에서 마피아넷 조회 + ckpt 저장)
    products = save_products_json(
        csv_path=input_csv,
        out_json_path=out_json,
        brand_instagram_volume_dict=brand_instagram_volume_dict,
        detail_category_top_frequency_dict=detail_category_top_frequency_dict,
        ckpt_brand=ckpt_brand_path,
        ckpt_brand_detail=ckpt_brand_detail_path,
    )

    # 2) Calc trend index CSV
    run_from_products(products, out_csv)

    # --- 3) 최종 병합 단계 추가 ---
    if original_json_path:
        merge_and_save_final_json(original_json_path, out_csv, final_json)

    print("=== PIPELINE DONE ===")


# ... 이하 생략 (main 호출 시 original_json_path를 넘겨주도록 수정) ...
    print(f"OUTPUT JSON: {out_json}")
    print(f"OUTPUT CSV : {out_csv}")


def parse_args():
    p = argparse.ArgumentParser(
        description="Run full pipeline: CSV -> JSON (with volumes) -> Trend Index CSV"
    )
    p.add_argument("--input_csv", required=True, help="Input CSV path")
    p.add_argument("--out_dir", default="out", help="Output directory (default: out)")
    p.add_argument("--json_name", default="products.json", help="Output JSON file name")
    p.add_argument("--result_csv_name", default="trend_index.csv", help="Output CSV file name")
    p.add_argument("--ckpt_brand", default="ckpt_brand_volume.json", help="Brand volume checkpoint file name")
    p.add_argument("--ckpt_brand_detail", default="ckpt_brand_detail_volume.json", help="Brand+detail volume checkpoint file name")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_trendindex_job(
        input_csv=args.input_csv,
        out_dir=args.out_dir,
        json_name=args.json_name,
        result_csv_name=args.result_csv_name,
        ckpt_brand=args.ckpt_brand,
        ckpt_brand_detail=args.ckpt_brand_detail,
    )
