"""
차트 퀴즈 채점 규칙(명세 5장). 임계값 ±5%·보유 20거래일은 백테스트 기본값과 같게 둔다.

내부 값 isMatch 는 화면에서 "같은 방향을 봤어요 / 다른 방향이었어요"로만 쓴다(정답·오답이라고 부르지 않는다).
"""
HOLD_DAYS = 20
THRESHOLD = 5.0
BASE_SCORE = 100
HINT_MULTIPLIER = 0.8
ANSWERS = ("UP", "FLAT", "DOWN")


def direction_of(ret_pct: float) -> str:
    if ret_pct >= THRESHOLD:
        return "UP"
    if ret_pct <= -THRESHOLD:
        return "DOWN"
    return "FLAT"


def streak_bonus(match_streak: int) -> int:
    """연속 일치 수(이번 것 포함)에 따른 보너스. 3회부터 +10, 5회부터 +20(상한)."""
    if match_streak >= 5:
        return 20
    if match_streak >= 3:
        return 10
    return 0


def score_of(is_match: bool, used_hint: bool, match_streak: int) -> int:
    """일치하지 않으면 0점. 일치하면 100 × (힌트 0.8) + 연속 보너스."""
    if not is_match:
        return 0
    base = BASE_SCORE * (HINT_MULTIPLIER if used_hint else 1.0)
    return int(round(base)) + streak_bonus(match_streak)
