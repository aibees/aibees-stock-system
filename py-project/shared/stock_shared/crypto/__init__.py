"""암호화폐 거래소 연동의 공용 계층.

py-stock-batch 의 app/ext_services/upbit/UpbitCcxt.py(d0cbcbd 에서 삭제)에 있던
차트(OHLCV) 조회만 여기로 복원했다. 주문/잔고는 아직 복원하지 않았다 — 예전 구현은
시장가 전용이었고, 새 구조(지정가 진입)가 확정되면 다시 설계한다.

  ohlcv   : 거래소 공통 캔들 페이징/프레임 변환
  upbit   : 업비트 KRW 마켓 캔들 조회 (최근 N봉 / 기간 페이징)
  binance : 바이낸스 USDT 마켓 캔들 조회 — 레짐(이평) 판단은 달러 기준이라 이쪽이 기본

이 패키지는 import 시점에 ccxt 를 가져오지 않는다(각 클라이언트가 생성자에서 지연 import).
"""
