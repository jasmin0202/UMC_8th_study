# util/helper.py
from __future__ import annotations
import csv
import time
import json
from typing import Iterable, List, Dict, Any, Union, Optional
import requests
import pandas as pd
import re

BASE = "https://ma-pia.net/keyword"
AJAX_ENDPOINT = f"{BASE}/keywordQ.php"  # JS가 호출하는 엔드포인트
AUX_INFO_ENDPOINT = "https://uy3w6h3mzi.execute-api.ap-northeast-2.amazonaws.com/Prod/hello"  # get_keyword_info()에서 호출
MAX_PER_RUN = 100

HEADERS = {
    "Origin": "https://ma-pia.net",
    "Referer": f"{BASE}/keyword.php",
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
}


_BRACKET_RE = re.compile(r"\[[^\]]*\]")  # [ ... ] 제거

# 브랜드명을 한글로 변환해주는 딕셔너리
BRAND_MAP = {
    "CHANEL": "샤넬",
    "Chanel": "샤넬",
    "chanel": "샤넬",
    "DIOR": "디올",
    "Dior": "디올",
    "GUCCI": "구찌",
}

def get_normalized_brand_name(raw_name: str) -> str:
    # 딕셔너리에 있으면 한글로 바꾸고, 없으면 원래 이름 사용
    return BRAND_MAP.get(raw_name.strip(), raw_name.strip())

def keyword_from_product_name(product_name: str) -> str:
    if not product_name:
        return ""
    s = str(product_name).strip()
    s = _BRACKET_RE.sub("", s)          # [] 블록 제거
    s = re.sub(r"\s+", " ", s).strip()  # 공백 정리
    return s

def build_keywords_from_csv(
    csv_path: str,
    *,
    name_col: str = "product_name",
) -> List[str]:
    keywords = set()
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = (row.get(name_col) or "").strip()
            kw = keyword_from_product_name(raw)
            if kw:
                keywords.add(kw)
    return sorted(keywords)

def _chunk(lst: List[str], n: int) -> List[List[str]]:
    return [lst[i:i+n] for i in range(0, len(lst), n)]


def _clean_num(x: str) -> int:
    """숫자 외의 문자를 제거하고 정수로 변환"""
    if not x:
        return 0
    # 숫자, 소수점 빼고 다 제거 (쉼표, 공백 등)
    s = re.sub(r"[^\d.]", "", str(x))
    if not s or s == ".":
        return 0
    try:
        # 소수점이 있을 수 있으니 float로 먼저 변환 후 반올림
        return int(round(float(s)))
    except (ValueError, TypeError):
        return 0


def _parse_keywordQ_response(raw: str) -> List[Dict[str, Any]]:
    """
    마피아넷 응답을 파싱. 데이터가 비어있거나 'fail'인 경우 체크.
    """
    if not raw or "fail" in raw:
        print(f"[Warning] 서버 응답이 비어있거나 실패함: {raw[:100]}")
        return []

    # 'success :' 이후의 데이터 추출
    parts = raw.split(":", 1)
    if len(parts) < 2:
        return []

    payload = parts[1].strip()
    items = [s for s in payload.split("|||") if s.strip()]

    rows = []
    for it in items:
        cols = it.split("///")
        if len(cols) < 3:
            continue
            
        # 데이터가 부족할 경우 빈 문자열로 채움
        while len(cols) < 9:
            cols.append("0")

        # 각 컬럼 추출
        keyword = cols[0].strip()
        pc_vol = _clean_num(cols[1])
        mob_vol = _clean_num(cols[2])
        
        # 🧪 디버깅용 출력: 실제로 숫자가 잡히는지 확인
        if pc_vol + mob_vol > 0:
            print(f"✅ 수집 성공: {keyword} -> PC: {pc_vol}, Mobile: {mob_vol}")
        else:
            print(f"❌ 수집 실패(0): {keyword} (Raw 데이터: {cols[1]}, {cols[2]})")

        rows.append({
            "키워드": keyword,
            "PC_월간검색수": pc_vol,
            "M_월간검색수": mob_vol,
            "검색수합계": pc_vol + mob_vol,
            "PC_월평균클릭수": _clean_num(cols[3]),
            "M_월평균클릭수": _clean_num(cols[4]),
            "PC_월평균클릭율": cols[5],
            "M_월평균클릭율": cols[6],
            "경쟁정도": cols[7],
            "월평균노출광고수": _clean_num(cols[8]),
        })
    return rows


def _fetch_aux_info(keyword: str, total_sum: int, session: requests.Session) -> Dict[str, Any]:
    """
    get_keyword_info()가 호출하는 보조 API 포맷을 그대로 사용.
    monthBlog / blogSaturation / shopCategory 등을 받아 병합.
    """
    params = {
        "keyword": keyword,
        "totalSum": total_sum,
        "time": int(time.time() * 1000),
    }
    try:
        r = session.get(AUX_INFO_ENDPOINT, params=params, timeout=15)
        r.raise_for_status()
        j = r.json()
        if j.get("status") and isinstance(j.get("result"), dict):
            return {
                "월간블로그발행": j["result"].get("monthBlog"),
                "블로그포화도": j["result"].get("blogSaturation"),
                "네이버쇼핑카테고리": j["result"].get("shopCategory"),
            }
    except Exception:
        pass
    return {"월간블로그발행": None, "블로그포화도": None, "네이버쇼핑카테고리": None}


def to_frontend_simple(df: pd.DataFrame) -> List[Dict[str, int]]:
    """
    [{keyword, pc, mobile, total}] 형태로 변환
    """
    out: List[Dict[str, int]] = []
    for _, r in df.iterrows():
        out.append({
            "keyword": r["키워드"],
            "total": int(r["검색수합계"]),
        })
    out.sort(key=lambda x: x["total"], reverse=True)
    return out


def to_frontend_rows(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    키워드별로 행(PC/M/합계) 분리 포맷
    [
      { "keyword": "A",
        "rows": [
          {"label":"월간검색수-pc","value":...},
          {"label":"월간검색수-mobile","value":...},
          {"label":"검색량합계","value":...}
        ]
      }, ...
    ]
    """
    payload: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        payload.append({
            "keyword": r["키워드"],
            "rows": [
                # {"label": "월간검색수-pc", "value": int(r["PC_월간검색수"])},
                # {"label": "월간검색수-mobile", "value": int(r["M_월간검색수"])},
                {"label": "검색량합계", "value": int(r["검색수합계"])},
            ]
        })
    payload.sort(key=lambda x: x["rows"][2]["value"], reverse=True)
    return payload


def fetch_ma_pia_volumes(
    keywords: Iterable[str],
    include_blog_info: bool = True,
    sleep_between_batches: float = 1.0,
    output: str = "df",   # "df" | "simple" | "rows"
) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
    """
    ma-pia.net/keyword/keyword.php 내부 AJAX( keywordQ.php )로 직접 수집.
    """
    # 1. 키워드 전처리 (공백 제거 및 빈 값 제외)
    kw_list = [k.strip() for k in keywords if str(k).strip()]
    
    if not kw_list:
        empty_df = pd.DataFrame(columns=[
            "키워드", "PC_월간검색수", "M_월간검색수", "검색수합계",
            "PC_월평균클릭수", "M_월평균클릭수", "PC_월평균클릭율", "M_월평균클릭율",
            "경쟁정도", "월평균노출광고수",
            "월간블로그발행", "블로그포화도", "네이버쇼핑카테고리",
        ])
        return _post_format(empty_df, output)

    # 2. 세션 준비 (쿠키/헤더 확보)
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get(f"{BASE}/keyword.php", timeout=15)
    except Exception as e:
        print(f"[Warning] 세션 확보 실패: {e}")

    batches = _chunk(kw_list, MAX_PER_RUN)
    all_rows: List[Dict[str, Any]] = []

    # 3. 배치 단위로 수집
    for i, group in enumerate(batches, start=1):
        # 특수문자 검사
        for bad in ["'", '"', "\\", ","]:
            if any(bad in k for k in group):
                raise ValueError(f"키워드에 사용할 수 없는 특수문자({bad}) 포함: {group}")

        dataq = ",".join(group)
        try:
            resp = s.post(AJAX_ENDPOINT, data={"DataQ": dataq}, timeout=30)
            resp.raise_for_status()
            
            # 파싱 및 블로그 정보 병합
            rows = _parse_keywordQ_response(resp.text)
            
            # 디버깅 로그 (필요 시 주석 처리)
            print(f"[Batch {i}] Status: {resp.status_code} | 수집 키워드 수: {len(rows)}")

            if include_blog_info:
                for r in rows:
                    aux = _fetch_aux_info(r["키워드"], r["검색수합계"], s)
                    r.update(aux)

            all_rows.extend(rows)
            
        except Exception as e:
            print(f"[Error] 배치 {i} 수집 중 오류 발생: {e}")

        # 마지막 배치가 아니면 대기
        if i < len(batches):
            time.sleep(sleep_between_batches)

    # 4. 데이터프레임 생성 및 정규화
    df = pd.DataFrame(all_rows)

    if not df.empty:
        # ⚠️ 중요: 대소문자 매칭 문제를 해결하기 위해 키워드를 대문자로 통일
        df["키워드"] = df["키워드"].str.strip().str.upper()
        
        df = (
            df.sort_values(["키워드"])
              .drop_duplicates(subset=["키워드"], keep="last")
              .sort_values("검색수합계", ascending=False)
              .reset_index(drop=True)
        )

    return _post_format(df, output)

def _post_format(df: pd.DataFrame, output: str) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
    if output == "simple":
        return to_frontend_simple(df)
    if output == "rows":
        return to_frontend_rows(df)
    return df

def min_max_0_100(series: pd.Series) -> pd.Series:
    """(값 - 최소) / (최대 - 최소) * 100 으로 정규화"""
    min_v = series.min()
    max_v = series.max()
    if max_v == min_v:
        return pd.Series([50.0] * len(series), index=series.index)
    return (series - min_v) / (max_v - min_v) * 100.0


_UNIT_MULTIPLIER = {
    "": 1,
    "백": 100,
    "천": 1_000,
    "만": 10_000,
    "억": 100_000_000,
}

# "2만 회", "3만개", "4.0만", "2만+", "약 2만", "2.3억" 같은 걸 처리
# - 기본 정책: 숫자 + (백/천/만/억) 1개만 지원
# - "회/개/명/건/원/좋아요" 같은 꼬리는 무시
# - 못 읽으면 None
_PATTERN = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*([백천만억]?)")

def parse_sales(value: Any) -> Optional[int]:
    if value is None:
        return None

    # 이미 숫자면 그대로
    if isinstance(value, (int,)):
        return int(value)
    if isinstance(value, float):
        return int(value)

    s = str(value).strip()
    if not s:
        return None

    # 공백 제거 + 쉼표 제거
    s = s.replace(",", "").replace(" ", "")

    # 흔한 꼬리/접두 제거(원하면 더 추가 가능)
    # 예: "2만회", "3만개", "약2만", "2만+", "2만좋아요"
    s = s.replace("+", "")
    for junk in ("약", "대략", "~", "회", "개", "명", "건", "원", "좋아요", "likes", "like"):
        s = s.replace(junk, "")

    m = _PATTERN.search(s)
    if not m:
        return None

    num_str, unit = m.group(1), m.group(2) or ""
    try:
        num = float(num_str)
    except ValueError:
        return None

    mul = _UNIT_MULTIPLIER.get(unit)
    if mul is None:
        return None

    return int(num * mul)