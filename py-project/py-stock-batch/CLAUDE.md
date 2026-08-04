# py-stock-batch — Claude 작업 규칙

## 브랜치 / PR 워크플로우
- `master` 에 직접 커밋하지 않는다. 항상 `claude/<주제>` 브랜치에서 작업한다.
- 논리적 변경이 끝날 때마다 `/pr` 로 처리한다:
  1) 변경요약(무엇을/왜, 한국어) 작성
  2) 관련 파일 스테이징 + conventional commit
  3) `git push` (토큰 인증)
  4) PR 생성 URL + 본문(변경요약) 출력 → 사용자가 PR 생성 클릭
- 시크릿(`*.key`, `.pr_token`)은 절대 새로 커밋하지 않는다.

## push 인증 (Cowork 샌드박스)
- 토큰은 `GH_TOKEN`(환경변수) 또는 리포 루트 `.pr_token`(gitignored)에서 읽는다.
- 원격: origin = github.com/aibees/py-stock-batch. PR 대상 = master.
- 샌드박스는 세션마다 초기화되므로, 토큰은 `.pr_token` 파일로 두면 세션 간 유지된다.
