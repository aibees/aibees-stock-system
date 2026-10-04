"""KIS(한국투자증권) 연동의 공용 계층.

py-stock-batch 와 py-naver-stock-theme 가 각자 갖고 있던 "자격증명 해석"과
"PyKis 클라이언트 생성"만 여기로 모았다. 시세/계좌 조회 같은 업무 메서드(KisEngine)는
두 앱의 구현이 서로 다르게 진화해서 아직 합치지 않았다.

  credentials : user_detail → KIS 자격증명 해석 (DB / 파일 / 유저 목록)
  client      : PyKis 인스턴스 생성 팩토리 (토큰 캐시 정책을 한 곳에 둔다)

이 패키지는 import 시점에 pykis 를 가져오지 않는다(client 가 함수 안에서 지연 import).
"""
