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

// 광고 제공자. 빌드 모드별 .env 의 VITE_AD_PROVIDER 로 고른다(없으면 'placeholder' = 자리표시 박스만).
//   'placeholder' | 'gpt-test' | 'adsense' | 'adfit'
//   'gpt-test' : 구글이 문서용으로 공개한 Ad Manager 샘플 광고 단위로 "진짜 광고처럼" 그린다.
//                계정·승인 없이 어느 도메인에서나 나오며 수익은 없다. 실광고 연동 전 웹 배포 확인용.
export const AD_PROVIDER = import.meta.env.VITE_AD_PROVIDER || 'placeholder';

export const AD_CONFIG = {
    // AdSense: client='ca-pub-XXXXXXXXXXXXXXXX', slots 는 광고 단위 ID.
    adsense: { client: '', slots: { side: '', gate: '', homeHero: '', homeMid: '', mobileInline: '', mobileBottom: '' } },
    // Kakao AdFit: 광고단위 ID('DAN-...'). 단위 생성 시 정한 크기와 아래 SIZES 가 같아야 한다.
    adfit: { units: { side: '', gate: '', homeHero: '', homeMid: '', mobileInline: '', mobileBottom: '' } },
    // Google Ad Manager(GPT) 공개 샘플 단위 — 테스트 크리에이티브만 나온다.
    gptTest: { unit: '/6355419/Travel/Europe/France/Paris' },
};

// 슬롯별 크기(px)
export const AD_SIZES = {
    side: { width: 160, height: 600 },
    gate: { width: 300, height: 250 },
    // fill: 부모 너비를 꽉 채우고 높이는 고른 소재(creatives)의 비율로 정한다(width/height 는 자리표시 기본값).
    // creatives: 칸 너비가 minBoxWidth 이상인 것 중 첫 번째를 쓴다(넓은 것부터).
    homeHero: {   // 홈: 시장 요약 아래 띠 배너(WORKER_USER 가 아닌 사용자). 375px 폭이면 높이 ≈ 54px
        width: 320, height: 50, fill: true,
        creatives: [{ width: 728, height: 90, minBoxWidth: 600 }, { width: 320, height: 50, minBoxWidth: 0 }],
    },
    homeMid: {    // 홈: 추천 성과 아래 두 번째 띠 배너
        width: 300, height: 50, fill: true,
        // 테스트 망은 같은 크기를 한 화면에 하나만 채워 준다 → homeHero(320×50/728×90)·하단(728×90)과 겹치지 않는 300×50.
        creatives: [{ width: 300, height: 50, minBoxWidth: 0 }],
    },
    mobileInline: { width: 320, height: 100 },   // 모바일 홈: 매수추천 카드 위
    mobileBottom: {   // 모바일 웹: 하단 탭바(Lnb) 아래. 375px 폭이면 높이 ≈ 46px
        width: 320, height: 50, fill: true,
        // 홈 띠 배너와 다른 소재 크기를 쓴다 — 테스트 망(gpt-test)은 같은 크기를 한 화면에 하나만 채워 준다.
        creatives: [{ width: 728, height: 90, minBoxWidth: 0 }],
    },
};

// 모바일 판정 폭. App.vue/Lnb 의 하단 탭바가 보이는 폭(640px 미만)과 같아야 한다.
export const MOBILE_MAX_WIDTH = 639;
// 앱(AdMob 320×50) 하단 배너 높이. 웹은 AdSlot 이 잰 높이를 --ad-bottom-fill-h 로 넘긴다(AdBottomBanner).
export const MOBILE_BOTTOM_BANNER_HEIGHT = 50;

// 이 메뉴들에 들어갈 때마다(AD_FREE 가 없는 사용자는) 먼저 광고를 봐야 한다.
export const AD_GATE_MENU_CODES = ['StockBuyTarget', 'StockInfo', 'ChartStock'];
// 게이트에서 "계속하기"가 열리기까지 대기 시간(초)
export const AD_GATE_SECONDS = 5;
// 시간 기반 면제는 없다 — 게이트 대상 메뉴는 들어갈 때마다 광고를 본다(useAdGate.js 의 1회용 통과권).

// 사이드 배너는 콘텐츠(최대 1200px) 양옆에 겹치지 않을 만큼 넓은 화면에서만 보인다.
//   1200 + 2 × (배너 160 + 여백 12) = 1544 → 여유를 두어 1560.
export const SIDE_BANNER_MIN_WIDTH = 1560;
