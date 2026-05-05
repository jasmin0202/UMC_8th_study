from typing import Any, List, Optional

# 정수로 변환하는 헬퍼
def _to_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None
    
def clamp_min(v: Optional[int], mn: int) -> Optional[int]:
    if v is None:
        return None
    return v if v >= mn else mn

# 100점 만점 정규화 함수
def minmax_score_100(values: List[Optional[int]]) -> List[Optional[float]]:
    """
    값이 클수록 높은 점수.
    min-max 정규화로 0~100 점수 부여.
    모든 값이 같으면 유효값은 전부 50점.
    """
    valid = [v for v in values if v is not None]
    out: List[Optional[float]] = [None] * len(values)

    if not valid:
        return out

    mn = min(valid)
    mx = max(valid)

    if mx == mn:
        for i, v in enumerate(values):
            out[i] = None if v is None else 50.0
        return out

    for i, v in enumerate(values):
        if v is None:
            out[i] = None
        else:
            out[i] = ((v - mn) / (mx - mn)) * 100.0

    return out

def nz(v: Optional[float]) -> float:
    return 0.0 if v is None else float(v)