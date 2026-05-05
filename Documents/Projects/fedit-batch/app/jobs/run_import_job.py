# app/jobs/run_import_job.py
# -*- coding: utf-8 -*-
import sys
import os
import csv
import json
import tempfile
import shutil
from typing import Optional, List, Dict, Any
from pathlib import Path

from app.common.helpers import parse_bool_str
from app.jobs.run_ranking_job import run_ranking_job
from app.jobs.run_trendindex_job import run_trendindex_job

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# --------------------------------------------------
# 최종 결과 병합 로직 (추가된 핵심 부분)
# --------------------------------------------------
def merge_trend_results_to_final_json(original_json_path: str, result_csv_path: str, final_output_path: str):
    """원본 JSON 데이터와 계산된 CSV의 점수들을 합쳐서 최종 JSON 생성"""
    if not os.path.exists(original_json_path) or not os.path.exists(result_csv_path):
        print(f"⚠️ 병합 실패: 원본 파일 혹은 결과 CSV가 없습니다.")
        return

    # 1. 원본 JSON 로드
    with open(original_json_path, "r", encoding="utf-8") as f:
        original_data = json.load(f)

    # 2. 결과 CSV 로드 (product_name 기준 매핑)
    trend_results = {}
    with open(result_csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trend_results[row["product_name"]] = row

    # 3. 데이터 업데이트
    final_output = []
    for item in original_data:
        name = item.get("product_name")
        if name in trend_results:
            res = trend_results[name]
            # 요구하신 형식에 맞게 데이터 타입 변환 및 필드명 매핑
            item.update({
                "search": int(float(res.get("search", 0))),
                "purchase_score": float(res.get("purchase_score", 0)),
                "category_score": float(res.get("category_score", 0)),
                "market_score": float(res.get("consumer_score", 0)), # CSV의 consumer -> market
                "rank": int(res.get("rank", 0)),
                "brand_score": 0.0,  # 필요시 로직 추가
                "is_platform": False
            })
        final_output.append(item)

    # 4. 저장
    with open(final_output_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    print(f"✨ 최종 JSON 병합 완료: {final_output_path}")

# --------------------------------------------------
# 공통 로더 및 유틸
# --------------------------------------------------
def read_json_rows(json_path: str) -> List[Dict[str, Any]]:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_rows_to_temp_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows: raise ValueError("데이터가 비어있습니다.")
    
    # 모든 키 추출 (헤더용)
    fieldnames = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)

    tmp = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", suffix=".csv", delete=False)
    writer = csv.DictWriter(tmp, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        normalized = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else (v if v is not None else "")) for k, v in row.items()}
        writer.writerow(normalized)
    tmp.close()
    return tmp.name

# --------------------------------------------------
# 메인 디스패치
# --------------------------------------------------
def run_dispatch_job(
    input_path: str,
    *,
    output_dir: str = "output",
    previous_snapshot_path: Optional[str] = None,
    date_str: str = "2026-03-w01",
) -> dict:
    ext = os.path.splitext(input_path)[1].lower()
    
    # 임시 CSV 변환 (Trend/Ranking 공통)
    if ext == ".json":
        rows = read_json_rows(input_path)
        # ranking/trend 여부 판정 (데이터 내부 필드 확인)
        # row[0]을 기준으로 판단하는 간단 로직
        is_platform = parse_bool_str(rows[0].get("is_platform") or rows[0].get("is_ranking"))
        effective_input_path = write_rows_to_temp_csv(rows)
    else:
        # CSV인 경우 판독 로직 (생략/기존 유지)
        is_platform = False 
        effective_input_path = input_path

    temp_csv_path = effective_input_path if ext == ".json" else None

    try:
        # 1. Ranking Job (플랫폼 데이터)
        if is_platform:
            result = run_ranking_job(
                current_csv_path=effective_input_path,
                output_dir=output_dir,
                previous_snapshot_path=previous_snapshot_path,
                date_str=date_str,
            )
            return {"job_type": "ranking", "result": result}

        # 2. Trend Job (자사 브랜드 데이터)
        trend_out_dir = os.path.join(output_dir, "trend")
        
        # run_trendindex_job 실행 (기존 코드와 호환)
        result = run_trendindex_job(
            input_csv=effective_input_path,
            out_dir=trend_out_dir,
            original_json_path=input_path # <--- 여기서 원본 경로 전달!
        )

        # 3. 최종 병합 (CSV 결과가 나왔으므로 원본 JSON과 합침)
        csv_result_path = os.path.join(trend_out_dir, "trend_index.csv")
        final_json_path = os.path.join(trend_out_dir, "final_trend_result.json")
        
        if ext == ".json":
            merge_trend_results_to_final_json(input_path, csv_result_path, final_json_path)

        return {
            "job_type": "trend",
            "input_path": input_path,
            "final_output": final_json_path,
            "result": result
        }

    finally:
        if temp_csv_path and os.path.exists(temp_csv_path):
            os.remove(temp_csv_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", default="output")
    parser.add_argument("--date_str", default="2026-03-w01")
    args = parser.parse_args()

    INPUT_FOLDER = os.path.join(BASE_DIR, "input") # 실제 경로에 맞춰 조정C:\Users\mycom\Documents\Projects\fedit-batch\app\input
    PROCESSED_FOLDER = os.path.join(BASE_DIR, "app", "processed")

    if not os.path.exists(PROCESSED_FOLDER): os.makedirs(PROCESSED_FOLDER)

    files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith((".csv", ".json"))]
    if not files:
        print(f"❌ '{INPUT_FOLDER}'에 파일이 없습니다.")
        sys.exit(1)

    target_filename = files[0]
    input_path = os.path.join(INPUT_FOLDER, target_filename)
    print(f"🚀 작업 시작: {target_filename}")

    try:
        res = run_dispatch_job(input_path, output_dir=args.output_dir, date_str=args.date_str)
        print(json.dumps(res, ensure_ascii=False, indent=2))

        # 성공 시 이동
        shutil.move(input_path, os.path.join(PROCESSED_FOLDER, target_filename))
        print(f"✅ 완료 및 이동: {target_filename}")

    except Exception as e:
        print(f"🔥 에러 발생: {e}")
        import traceback
        traceback.print_exc()