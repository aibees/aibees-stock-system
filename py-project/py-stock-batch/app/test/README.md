# app/test — 연구·검증 스크립트

## bt_* 파일 (연구팀 백테스트)
- 연구팀이 가설 검증에 쓰는 일회성 백테스트·탐색 스크립트다. **실 운영(배치·워커·웹)과 무관하며 배포하지 않는다.**
- `py-stock-batch/.gitignore` 의 `app/test/bt_*` 로 새 파일은 커밋하지 않고,
  `py-project/.dockerignore` 의 `**/app/test/bt_*` 로 도커 이미지(py-stock-batch / worker)에도 넣지 않는다.
- 운영 코드는 `bt_*` 를 import 하면 안 된다. 예외로 `collect_wave2_minutes.py`(연구용 수집 스크립트)가
  `bt_wave2_fake_rise`, `bt_wave2_trendline` 을 import 한다 — 컨테이너 안에서는 실행되지 않는다.
- 이미 git 에 올라간 일부 bt_* 는 계속 추적 상태다(ignore 는 새 파일에만 적용).
