/**
 * 메뉴 표시 이름. 메뉴명은 서버 DB 값이라, 서버 값이 바뀌기 전에도 화면에는 정리된 표현을 보여준다.
 * '매수추천'은 투자 권유로 읽힐 수 있어 '주목 종목'으로 표시한다.
 */
export const menuLabel = (m) => (
    String(m?.menu_path ?? '').endsWith('buy-target') ? '주목 종목' : (m?.menu_title || m?.menu_name || '')
);
