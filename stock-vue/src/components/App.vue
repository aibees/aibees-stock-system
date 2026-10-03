<script setup>
import Lnb from './common/Lnb.vue';
</script>

<template>
  <!-- app-shell: 하단 탭바 여백을 라우터 화면에만 주기 위한 앵커.
       Lnb 가 렌더하는 탭바 자체는 position:fixed 라 이 여백 대상이 아니다. -->
  <div class="app-shell">
    <Lnb />
    <router-view />
  </div>
</template>

<style lang="scss">
@use '@@/__variables.scss' as *;

:root {
  /* 모바일 하단 탭바(#comm-lnb)의 실제 높이. 바 자신과 각 화면의 하단 여백이
   * 같은 값을 보도록 한 곳에서 정의한다 — 따로 쓰면 반드시 한쪽이 어긋난다.
   * 홈 인디케이터(safe-area-inset-bottom)를 더해야 기기별로 맞는다. */
  --lnb-height: 3.5rem;
  --lnb-total: calc(var(--lnb-height) + env(safe-area-inset-bottom, 0px));
}

html,
body {
  /* 가로 넘침 방어. 안쪽 요소가 뷰포트보다 넓어지면 body 가 함께 넓어져
   * 화면 전체가 좌우로 밀리고 잘린 것처럼 보인다(정렬 칩이 대표 사례).
   * 넘치는 요소는 개별로 고치되, 하나 놓쳐도 전체 레이아웃이 깨지지 않게 막아둔다. */
  max-width: 100%;
  overflow-x: hidden;
}

body {
  height: 100%;
  background-color: #f7f7f7;
  margin: 0;

}
#app {
  height: 100%;
  font-family: "맑은 고딕", "Malgun Gothics", sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #f7f7f7;

  /* 상하좌우 노치 및 홈 바 영역 자동 대응.
   * padding-bottom 은 여기서 주지 않는다 — 하단 탭바가 position:fixed 로 그
   * 영역을 이미 덮고 있어서, #app 에까지 주면 바 아래에 빈 띠가 한 겹 더 생긴다.
   * 홈 인디케이터 대응은 바 자신(#comm-lnb)이 padding-bottom 으로 처리한다. */
  padding-top: env(safe-area-inset-top);
  padding-left: env(safe-area-inset-left);
  padding-right: env(safe-area-inset-right);
}

/* ── iOS 입력 포커스 시 자동 확대 방지 ─────────────────────────────────────
 * iOS Safari/WKWebView 는 폰트가 16px 미만인 입력요소에 포커스가 가면 화면을
 * 자동으로 확대한다. 그 확대가 라우팅 후에도 남아서 "화면 이동 시 갑자기
 * 확대되는" 것처럼 보인다(로그인 아이디/비번 입력에서 특히 잘 재현).
 *
 * 막는 방법이 둘인데,
 *   (a) viewport meta 에 maximum-scale=1 / user-scalable=no
 *   (b) 입력요소 폰트를 16px 이상으로
 * (a) 는 핀치줌까지 막아 저시력 사용자의 확대 수단을 없애므로 쓰지 않는다.
 * 폰 폭에서만 올려 데스크톱 디자인은 그대로 둔다.
 *
 * #app 을 앞에 붙이는 이유: 각 화면의 scoped 스타일(.field-input[data-v-x] 등)이
 * 클래스+속성이라 맨 요소 선택자보다 우선순위가 높다. ID 를 한 단계 얹으면
 * !important 없이 확실히 이긴다.
 * ※ 16px 은 iOS 의 판정 기준값이라 15.9px 로 낮추면 다시 확대된다. */
@media screen and (max-width: 639px) {
  #app input,
  #app select,
  #app textarea {
    font-size: 16px;
  }
}

/* 하단 탭바가 보이는 폭(=탭바가 display:none 이 되는 640px 미만)에서만
 * 라우터 화면 끝에 바 높이만큼 여백을 준다. 이게 없으면 각 화면의 마지막
 * 3.5rem 이 고정 탭바에 가려진다 — 메뉴 목록 맨 아래 항목이 잘려 보이던 원인.
 *
 * 탭바(#comm-lnb)와 웹 상단바(#comm-lnb-web)는 app-shell 의 직계 자식이지만
 * 여백 대상이 아니라 제외한다. 나머지 직계 자식이 곧 router-view 가 그린 화면이다. */
@media screen and (max-width: 639px) {
  .app-shell > :not(#comm-lnb):not(#comm-lnb-web) {
    padding-bottom: var(--lnb-total);
  }
}
</style>