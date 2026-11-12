"""
운용모드 코드 — master_trade_mode.mode_code / user_trade_mode.active_mode 등에 저장되는 값.

예전에는 M0·M1·M2 처럼 번호로 불렀는데, 번호가 의미를 담지 못해 모드가 추가·폐기될
때마다 번호를 밀어야 했다(sql/04). 2026-11 부터 의미 있는 영문 코드를 쓴다(sql/54).

  HALT        매매정지   신규 매수만 멈추고 보유분 매도는 계속한다
  RECO        추천매수   20:00 배치 매수타겟을 익일 매수 (RecoStrategy)
  ETF_SWITCH  ETF 교대   KODEX 코스피100 / 인버스 30분봉 운용 (EtfSwitchStrategy)

DB 값을 바꾸지 않고 코드만 바꾸면 worker 가 모드를 못 찾는다 → 배포 전에 sql/54 를 먼저 적용한다.
"""

HALT = "HALT"
RECO = "RECO"
ETF_SWITCH = "ETF_SWITCH"

#: 옛 번호 코드 → 새 코드. **배포 순서 사고 대비용 안전장치**다.
#:   sql/54 보다 코드가 먼저 뜨면 DB 에 'M0' 이 남아 있는데, worker 는 모르는 모드를
#:   기본 모드(RECO)로 돌리므로 매매정지 유저의 신규 매수가 다시 나간다.
#:   읽는 쪽에서 normalize() 로 한 번 더 걸러 그 상황을 막는다.
#:   sql/54 적용이 끝난 모든 환경에서 번호 코드가 0건임을 확인하면 지워도 된다.
LEGACY_ALIASES = {"M0": HALT, "M1": RECO, "M2": ETF_SWITCH}


def normalize(code):
    """DB 에서 읽은 모드 코드를 새 코드로. 옛 번호 코드면 바꾸고, 그 외는 그대로 돌려준다."""
    if code is None:
        return None
    code = str(code)
    return LEGACY_ALIASES.get(code, code)
