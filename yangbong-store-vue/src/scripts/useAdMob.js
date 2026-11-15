/**
 * AdMob 네이티브 배너 — 네이티브(iOS/Android) 앱 전용.
 *
 * @capacitor-community/admob v8 사용. 웹(브라우저)에서는 아무 것도 하지 않는다 —
 * Capacitor.isNativePlatform() 로 분기하고, 플러그인 자체도 네이티브일 때만 동적 import 한다
 * (웹 번들에 광고 코드가 실리지 않게).
 *
 * ── 역할 분담 ──────────────────────────────────────────────────────────────
 * 이 모듈은 "AdMob SDK 와 배너 한 장"만 다룬다. **언제 광고를 보일지는 여기서 정하지 않는다.**
 *   - 노출 여부(권한 AD_FREE, 로그인 화면, 광고 전체 스위치)는 useAds.useShowAds() 가 정한다.
 *   - 그 판정을 받아 이 모듈을 부르는 곳은 AdBottomBanner.vue 하나다.
 *   - 레이아웃(탭바를 배너 위로 올리고 화면 하단 여백을 늘리는 일)도 기존 html.has-bottom-ad
 *     규칙(App.vue)이 한다. 배너는 그 규칙이 예약한 하단 50px 칸 위에 그대로 겹쳐 그려진다.
 * 여기에 라우트/권한 판단을 또 두면 AD_FREE 사용자에게 광고가 나가는 식으로 두 곳이 어긋난다.
 *
 * ── 광고 크기 ──────────────────────────────────────────────────────────────
 * 적응형이 아니라 표준 배너(320×50)를 쓴다. 예약 영역이 adConfig.MOBILE_BOTTOM_BANNER_HEIGHT(50)로
 * 고정이라, 높이가 달라지는 적응형 배너를 쓰면 탭바 위치/여백이 어긋난다.
 *
 * ── 광고 단위 ID 와 테스트 모드 ─────────────────────────────────────────────
 * 실제 광고 단위 ID 는 .env.prd 에서만 주입한다. 없으면 Google 공식 테스트 광고가 나간다.
 *
 *   VITE_ADMOB_BANNER_ID_IOS      iOS 배너 광고 단위 ID
 *   VITE_ADMOB_BANNER_ID_ANDROID  Android 배너 광고 단위 ID
 *   VITE_ADMOB_ENABLED=false      네이티브 광고 끄기(기존 자리표시로 돌아간다)
 *   VITE_ADMOB_TESTING=true       실ID 가 있어도 테스트 광고로 강제
 *
 * isTesting=true 이면 플러그인이 넘겨받은 adId 를 무시하고 Google 테스트 단위로 바꿔 끼운다
 * (iOS 는 무조건, Android 는 테스트 기기로 등록된 경우 Google 이 테스트 광고만 내보낸다).
 * 그래서 개발 중에 실ID 가 섞여 들어와도 자기 광고를 눌러 계정이 정지되는 사고가 구조적으로 없다.
 * dev 서버(DEV)와 --mode dev 빌드는 항상 테스트 모드다.
 *
 * ── 보상형 광고(광고 게이트) ───────────────────────────────────────────────
 * 매수추천상세/개별주식/개별차트(adConfig.AD_GATE_MENU_CODES) 진입 전 AdGate.vue 가 쓴다.
 * 광고 단위는 VITE_ADMOB_REWARDED_ID_IOS / VITE_ADMOB_REWARDED_ID_ANDROID 로 주입하고,
 * 테스트 모드/ENABLED 규칙은 배너와 같다.
 */
import { ref } from 'vue';
import { Capacitor } from '@capacitor/core';

// Google 공식 테스트 광고 단위. https://developers.google.com/admob/android/test-ads
const TEST_UNIT_ID = {
    banner:   { ios: 'ca-app-pub-3940256099942544/2934735716', android: 'ca-app-pub-3940256099942544/6300978111' },
    rewarded: { ios: 'ca-app-pub-3940256099942544/1712485313', android: 'ca-app-pub-3940256099942544/5224354917' },
};
// 광고 종류별 실제 단위 ID 를 담는 환경변수 이름
const ENV_KEY = {
    banner:   { ios: 'VITE_ADMOB_BANNER_ID_IOS',   android: 'VITE_ADMOB_BANNER_ID_ANDROID' },
    rewarded: { ios: 'VITE_ADMOB_REWARDED_ID_IOS', android: 'VITE_ADMOB_REWARDED_ID_ANDROID' },
};

const isTrue = (v) => String(v ?? '').trim().toLowerCase() === 'true';
const isFalse = (v) => String(v ?? '').trim().toLowerCase() === 'false';

/**
 * 플랫폼/환경변수로 이번 실행의 광고 설정을 정한다. 순수 함수 — 플러그인·DOM 에 의존하지 않아
 * 단위 검증이 가능하다.
 *
 * @param {{platform: string, env: Record<string, any>, kind?: 'banner'|'rewarded'}} p
 * @returns {{enabled: false, reason: string} | {enabled: true, adId: string, isTesting: boolean}}
 */
export function resolveAdConfig({ platform, env, kind = 'banner' }) {
    if (platform !== 'ios' && platform !== 'android') {
        return { enabled: false, reason: `지원하지 않는 플랫폼(${platform})` };
    }
    if (isFalse(env.VITE_ADMOB_ENABLED)) {
        return { enabled: false, reason: 'VITE_ADMOB_ENABLED=false' };
    }

    const realId = String(env[ENV_KEY[kind][platform]] ?? '').trim();

    // dev 서버 / --mode dev 빌드 / 명시적 강제 → 항상 테스트 광고.
    const forceTest = isTrue(env.VITE_ADMOB_TESTING) || !!env.DEV || env.MODE === 'dev';

    if (realId && !forceTest) {
        return { enabled: true, adId: realId, isTesting: false };
    }
    // adId 는 필수 인자라 채워 넘기지만, isTesting=true 라 플러그인이 어차피 테스트 단위로 바꾼다.
    return { enabled: true, adId: realId || TEST_UNIT_ID[kind][platform], isTesting: true };
}

const cachedConfig = {};   // kind → 설정. 첫 호출 때만 구한다
/** 이번 실행의 광고 설정. import.meta.env 는 첫 호출 때만 읽는다(Node 단위 검증에서 모듈만 import 해도 안전하게). */
const getConfig = (kind = 'banner') => {
    if (cachedConfig[kind] === undefined) {
        cachedConfig[kind] = Capacitor.isNativePlatform()
            ? resolveAdConfig({ platform: Capacitor.getPlatform(), env: import.meta.env, kind })
            : { enabled: false, reason: '웹 환경' };
    }
    return cachedConfig[kind];
};

/** 이 실행에서 네이티브 AdMob 이 켜져 있는가. false 면 호출부는 기존 자리표시 동작을 그대로 쓴다. */
export const isNativeAdsEnabled = () => getConfig().enabled;

/**
 * 배너 상태 — 호출부가 레이아웃을 맞추는 데 쓴다.
 *   idle     아직 요청 전
 *   loading  요청 중(예약 영역은 유지해서 레이아웃이 튀지 않게)
 *   loaded   광고가 그려짐
 *   failed   광고가 없음(채워지지 않음/동의 없음/초기화 실패) → 호출부가 예약 영역을 접는다
 */
export const bannerState = ref('idle');

// ── SDK 초기화 ────────────────────────────────────────────────────────────
let resolveReady;
const ready = new Promise((resolve) => { resolveReady = resolve; });   // true/false
let initStarted = false;
let admob = null;   // 동적 import 한 플러그인 모듈

/**
 * AdMob SDK 를 초기화한다(ATT → initialize → 동의). 한 번만 실행된다.
 * 배너는 여기서 만들지 않는다 — showBottomBanner() 가 이 초기화가 끝나길 기다렸다가 만든다.
 */
export async function initAdMob() {
    if (initStarted) return ready;
    initStarted = true;

    const cfg = getConfig();
    if (!cfg.enabled) {
        console.log('[admob] 비활성:', cfg.reason);
        resolveReady(false);
        return ready;
    }

    try {
        admob = await import('@capacitor-community/admob');
        const { AdMob, AdmobConsentStatus, BannerAdPluginEvents } = admob;
        const platform = Capacitor.getPlatform();

        // iOS: 추적 동의(ATT). 광고 요청 전에 받아야 개인화 광고가 나간다. 한 번 결정되면 다시 안 묻는다.
        if (platform === 'ios') {
            try {
                const { status } = await AdMob.trackingAuthorizationStatus();
                if (status === 'notDetermined') await AdMob.requestTrackingAuthorization();
            } catch (e) {
                console.warn('[admob] ATT 요청 실패(무시):', e?.message);
            }
        }

        await AdMob.initialize();

        // 개인정보 동의(UMP). 한국에서는 보통 NOT_REQUIRED 지만 EEA 등에서는 폼이 필요하다.
        // 동의 "조회 자체가 실패"하는 경우(AdMob 쪽 동의 메시지/앱 설정이 아직 없거나 네트워크 오류 등)에는
        // 광고를 포기하지 않고 계속 진행한다. 여기서 throw 하면 초기화 전체가 실패 처리돼 배너/보상형이
        // 전부 꺼진다(실제로 "Request consent info failed" 로 광고가 하나도 안 나온 적이 있다).
        // 동의가 필요한 지역에서는 SDK 가 스스로 광고를 제한하므로, 확실히 거부된 경우만 막는다.
        try {
            let consent = await AdMob.requestConsentInfo();
            if (consent.isConsentFormAvailable && consent.status === AdmobConsentStatus.REQUIRED) {
                consent = await AdMob.showConsentForm();
            }
            if (!consent.canRequestAds) {
                console.warn('[admob] 동의가 없어 광고를 요청하지 않습니다.');
                bannerState.value = 'failed';
                resolveReady(false);
                return ready;
            }
        } catch (e) {
            console.warn('[admob] 동의 정보 조회 실패 — 광고 요청은 계속 시도합니다:', e?.errorMessage ?? e?.message ?? e);
        }

        await AdMob.addListener(BannerAdPluginEvents.Loaded, () => { bannerState.value = 'loaded'; });
        await AdMob.addListener(BannerAdPluginEvents.FailedToLoad, (err) => {
            console.warn('[admob] 배너 로드 실패:', err?.code, err?.message);
            bannerState.value = 'failed';   // 광고가 없는데 빈 칸만 남지 않게. SDK 가 재시도해 Loaded 가 오면 되돌아온다.
        });

        console.log(`[admob] 초기화 완료 (platform=${platform}, testing=${cfg.isTesting})`);
        resolveReady(true);
    } catch (e) {
        // 광고 실패가 앱 사용을 막으면 안 된다.
        console.error('[admob] 초기화 실패', e);
        bannerState.value = 'failed';
        resolveReady(false);
    }
    return ready;
}

// ── 하단 배너 ─────────────────────────────────────────────────────────────
let wantVisible = false;
let created = false;      // showBanner 를 한 번이라도 불렀는가(이후엔 resume 으로 다시 켠다)
let visible = false;
let queue = Promise.resolve();   // 보이기/숨기기 요청이 빠르게 겹쳐도 순서대로만 실행되게 직렬화

const apply = async () => {
    if (!(await ready)) return;   // 초기화 전이면 여기서 기다린다. 실패했으면 아무 것도 안 한다.
    const { AdMob, BannerAdSize, BannerAdPosition } = admob;
    const cfg = getConfig();

    if (wantVisible && !visible) {
        if (created) {
            await AdMob.resumeBanner();
        } else {
            bannerState.value = 'loading';
            await AdMob.showBanner({
                adId: cfg.adId,
                isTesting: cfg.isTesting,
                adSize: BannerAdSize.BANNER,            // 320×50. 적응형이 아닌 이유는 파일 상단 주석 참고
                position: BannerAdPosition.BOTTOM_CENTER,
                margin: 0,   // 플러그인이 홈 인디케이터/시스템바 인셋을 이미 더한다. 탭바는 HTML 쪽이 배너 위로 올린다.
            });
            created = true;
        }
        visible = true;
    } else if (!wantVisible && visible) {
        await AdMob.hideBanner();
        visible = false;
    }
};

const enqueue = () => {
    queue = queue.then(apply).catch((e) => {
        console.warn('[admob] 배너 표시 전환 실패:', e?.message ?? e);
    });
    return queue;
};

/** 하단 배너를 보인다(처음이면 만든다). 초기화가 끝나지 않았다면 끝난 뒤에 실행된다. */
export const showBottomBanner = () => { wantVisible = true; return enqueue(); };

/** 하단 배너를 숨긴다(파괴하지 않는다 — 다시 보일 때 resume). */
export const hideBottomBanner = () => { wantVisible = false; return enqueue(); };

// ── 보상형 광고 ───────────────────────────────────────────────────────────
// 플러그인의 showRewardVideoAd 는 "보상을 받았을 때만" resolve 하고, 보상 없이 닫으면 영원히 pending 이다.
// 그래서 Rewarded / Dismissed / FailedToShow 이벤트를 함께 보고 결과를 직접 정한다.
const REWARDED_LOAD_TIMEOUT_MS = 10000;

/**
 * 보상형 광고를 미리 불러온다. 광고는 로드에 몇 초 걸리므로 보여주기 전에 호출해 둔다.
 * @returns {Promise<boolean>} 불러왔으면 true. 비활성/초기화 실패/로드 실패/시간 초과는 false.
 */
export async function loadRewardedAd() {
    const cfg = getConfig('rewarded');
    if (!cfg.enabled) return false;

    const load = (async () => {
        // 푸시 팝업 뒤로 미뤄 둔 초기화가 아직 시작 전일 수 있다. 멱등이라 여기서 불러도 안전하다.
        if (!(await initAdMob())) return false;
        try {
            await admob.AdMob.prepareRewardVideoAd({ adId: cfg.adId, isTesting: cfg.isTesting });
            return true;
        } catch (e) {
            console.warn('[admob] 보상형 광고 로드 실패:', e?.code, e?.message ?? e);
            return false;
        }
    })();
    const timeout = new Promise((resolve) => setTimeout(() => resolve(false), REWARDED_LOAD_TIMEOUT_MS));
    return Promise.race([load, timeout]);
}

/**
 * 불러온 보상형 광고를 보여준다. 한 번 보여주면 그 광고는 소진되므로, 다시 보여주려면 loadRewardedAd 부터.
 * @returns {Promise<'rewarded'|'dismissed'|'failed'>}
 *   rewarded  끝까지 시청해 보상을 받음 / dismissed  보상 없이 닫음 / failed  재생 실패
 */
export async function showRewardedAd() {
    const { AdMob, RewardAdPluginEvents } = admob ?? {};
    if (!AdMob) return 'failed';

    const handles = [];
    try {
        return await new Promise((resolve) => {
            let settled = false;
            const done = (result) => { if (!settled) { settled = true; resolve(result); } };
            (async () => {
                handles.push(await AdMob.addListener(RewardAdPluginEvents.Rewarded, () => done('rewarded')));
                handles.push(await AdMob.addListener(RewardAdPluginEvents.Dismissed, () => done('dismissed')));
                handles.push(await AdMob.addListener(RewardAdPluginEvents.FailedToShow, (e) => {
                    console.warn('[admob] 보상형 광고 재생 실패:', e?.code, e?.message);
                    done('failed');
                }));
                await AdMob.showRewardVideoAd();   // 보상 시 resolve(이미 Rewarded 이벤트로 처리됨), 재생 불가면 reject
                done('rewarded');
            })().catch((e) => {
                console.warn('[admob] 보상형 광고 표시 실패:', e?.message ?? e);
                done('failed');
            });
        });
    } finally {
        handles.forEach((h) => h?.remove?.());
    }
}
