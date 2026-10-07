/**
 * 광고 설정.
 *
 * 노출 여부는 광고망과 무관하게 기능 플래그 AD_FREE 로 정한다(useAccess.hasFeature).
 * 이 파일은 "어떤 광고를, 어떤 메뉴 앞에서, 얼마나" 만 담는다.
 */

// 광고 전체 스위치. false 면 사이드/모바일 배너와 진입 게이트가 모두 꺼진다.
// ※ 광고 계정을 연동하기 전에는 배너가 자리표시 박스("AD")로 보이므로, 운영에 올릴 때
//   실제 광고가 준비되지 않았다면 false 로 두는 편이 낫다.
export const AD_ENABLED = true;

// 광고 제공자. 계정/승인이 나오기 전까지 'placeholder' (자리표시 박스만 그린다).
//   'placeholder' | 'adsense' | 'adfit'
export const AD_PROVIDER = 'placeholder';

export const AD_CONFIG = {
    // AdSense: client='ca-pub-XXXXXXXXXXXXXXXX', slots 는 광고 단위 ID.
    adsense: { client: '', slots: { side: '', gate: '', homeHero: '', mobileInline: '', mobileBottom: '' } },
    // Kakao AdFit: 광고단위 ID('DAN-...'). 단위 생성 시 정한 크기와 아래 SIZES 가 같아야 한다.
    adfit: { units: { side: '', gate: '', homeHero: '', mobileInline: '', mobileBottom: '' } },
};

// 슬롯별 크기(px)
export const AD_SIZES = {
    side: { width: 160, height: 600 },
    gate: { width: 300, height: 250 },
    homeHero: { width: 300, height: 250 },       // 홈: 최우선 타겟 카드 자리(WORKER_USER 가 아닌 사용자)
    mobileInline: { width: 320, height: 100 },   // 모바일 홈: 매수추천 카드 위
    mobileBottom: { width: 320, height: 50 },    // 모바일: 하단 탭바(Lnb) 아래
};

// 모바일 판정 폭. App.vue/Lnb 의 하단 탭바가 보이는 폭(640px 미만)과 같아야 한다.
export const MOBILE_MAX_WIDTH = 639;
export const MOBILE_BOTTOM_BANNER_HEIGHT = 50;

// 이 메뉴들에 들어가려면(AD_FREE 가 없는 사용자는) 먼저 광고를 봐야 한다.
export const AD_GATE_MENU_CODES = ['StockBuyTarget', 'StockInfo', 'ChartStock'];
// 게이트에서 "계속하기"가 열리기까지 대기 시간(초)
export const AD_GATE_SECONDS = 5;
// 한 번 본 뒤 이 시간(분) 동안은 다시 묻지 않는다. 0 이면 진입할 때마다 본다.
export const AD_GATE_PASS_MINUTES = 30;

// 사이드 배너는 콘텐츠(최대 1200px) 양옆에 겹치지 않을 만큼 넓은 화면에서만 보인다.
//   1200 + 2 × (배너 160 + 여백 12) = 1544 → 여유를 두어 1560.
export const SIDE_BANNER_MIN_WIDTH = 1560;
