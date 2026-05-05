# string -> 숫자로 가격 바꾸는거
from typing import Any, Optional

TRUE_SET = {"true", "1", "y", "yes", "t"}
FALSE_SET = {"false", "0", "n", "no", "f"}

# is_platform 판정 헬퍼
def parse_bool_str(value: Any) -> Optional[bool]:
    """
    CSV에서 읽은 is_platform 값을 bool로 정규화.
    비어있으면 None 반환.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    s = str(value).strip().lower()

    if s == "":
        return None
    if s in TRUE_SET:
        return True
    if s in FALSE_SET:
        return False

    raise ValueError(f"지원하지 않는 is_platform 값: {value}")
