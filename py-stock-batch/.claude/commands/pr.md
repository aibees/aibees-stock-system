현재 작업 변경분을 브랜치에 커밋·push 하고 PR 을 준비하라. $ARGUMENTS 가 있으면 브랜치/PR 주제로 사용.

절차:
1. 현재 브랜치가 `claude/*` 가 아니면 `claude/<주제>` 로 새로 만들고 체크아웃.
2. `git status` 로 변경 확인 → 시크릿(`*.key`, `.pr_token`) 제외하고 관련 파일만 스테이징.
3. 변경요약(무엇을/왜, 한국어)을 작성해 conventional commit 으로 커밋.
4. 토큰을 `GH_TOKEN`(env) 또는 `./.pr_token` 에서 읽어 1회성으로 push:
   `git push "https://<TOKEN>@github.com/aibees/py-stock-batch.git" HEAD:<branch>`
   - 토큰을 git remote/config 에 영구 저장하거나 로그에 출력하지 말 것.
   - 토큰이 없으면 커밋까지만 하고 `.pr_token` 생성 방법을 안내.
5. push 성공 시 출력:
   - PR 생성 URL: `https://github.com/aibees/py-stock-batch/compare/master...<branch>?expand=1`
   - PR 제목 + 본문(변경요약) — 붙여넣기용
6. 시크릿/토큰은 절대 커밋·로그에 노출하지 말 것.
