"""매수·매도 타점(진입/손절/목표/손익비) 공통 형식."""


def r(v):
    return None if v is None else round(float(v), 2)


def plan(side: str, entry: float, stop: float, target: float, **extra) -> dict:
    """side: 'buy' | 'sell'.

    sell 은 국내 현물이라 공매도 진입이 아니라 "보유분 정리·신규 매수 회피" 기준으로 읽는다.
    손익비 = 목표까지 거리 / 손절까지 거리(진입가 기준).
    """
    if side == 'buy':
        risk, reward = entry - stop, target - entry
    else:
        risk, reward = stop - entry, entry - target
    out = {
        'side': side,
        'entry': r(entry),
        'stop': r(stop),
        'target': r(target),
        'loss_pct': r(risk / entry * 100) if entry else None,
        'gain_pct': r(reward / entry * 100) if entry else None,
        'rr': r(reward / risk) if risk > 0 else None,
    }
    out.update({k: (r(v) if isinstance(v, float) else v) for k, v in extra.items()})
    return out
