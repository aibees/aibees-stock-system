/**
 * 보상형 광고 공통 실행기 — 모든 호출처(AdGate.vue, honey-store.watchAd)가 이것만 쓴다.
 *
 * 흐름: 시작 → 불러오는 중(전체 덮개) → 표시(네이티브 광고가 덮개 위에 뜬다) → 보상/닫힘/실패/시간 초과 → 덮개 닫힘
 * 덮개(RewardedAdOverlay.vue)는 App.vue 에 한 번 두고, 여기의 rewardedAdState 를 본다. 화면을 옮겨도 이어진다.
 *
 * 꿀은 앱이 주지 않는다. Google 이 서버(/api/v1/honey/admob-ssv)에 시청 완료를 알려야 쌓인다.
 * 그래서 결과가 rewarded 여도 꿀 반영은 honey-store.afterAdReward 가 요약을 다시 받아 확인한다.
 *
 * 환경별:
 *   앱(네이티브 AdMob)  실제 광고
 *   목업(npm run dev:mock) 덮개 안에 가짜 광고를 그려 끝까지 보기/닫기/실패를 고를 수 있다.
 *                        끝까지 보면 /api/v1/honey/mock-ad 를 불러 서버 SSV 를 흉내 낸다(응답은 쓰지 않는다 — 실제와 같게 요약을 다시 받아 본다).
 *   웹(광고 없음)       'unavailable' — 호출처는 광고 없이 진행하거나 '앱 전용'으로 보인다.
 */
import { reactive } from 'vue';
import aibeesApi from '@scripts/aibeesApi.js';
import { MOCK_ENABLED } from '@scripts/mock/mockApi.js';
import { isNativeAdsEnabled, loadRewardedAd, showRewardedAd } from '@scripts/useAdMob.js';
import { assUserSession } from '@scripts/stores/user-stores.js';

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const useMock = () => MOCK_ENABLED && !isNativeAdsEnabled();

/**
 * 덮개·알림 상태(전역 하나).
 *   phase   null | 'loading'(불러오는 중) | 'showing'(재생 중) | 'checking'(꿀 확인 중)
 *   notice  광고가 끝난 뒤 잠깐 보이는 한 줄 안내(화면이 바뀌어도 보이도록 전역)
 *   mock    목업 가짜 광고를 그릴지
 */
export const rewardedAdState = reactive({ phase: null, notice: '', noticeKey: 0, mock: false });
let mockAnswer = null;

/** 이 실행에서 보상형 광고를 쓸 수 있는가(앱 또는 목업). */
export const rewardedAdSupported = () => isNativeAdsEnabled() || MOCK_ENABLED;

/** 광고가 끝난 뒤 안내 한 줄. 덮개 컴포넌트가 몇 초 보이고 지운다. */
export const notifyAd = (msg) => {
    rewardedAdState.notice = msg || '';
    rewardedAdState.noticeKey = Date.now();
};

/** 꿀 확인 중 덮개(honey-store 가 요약을 다시 받는 동안). */
export const setAdChecking = (on) => { rewardedAdState.phase = on ? 'checking' : null; };

// SSV 용 사용자. 로그인하지 않았으면 광고는 보여도 서버가 꿀을 주지 않는다.
const ssvOpts = (customData) => {
    const uid = assUserSession().user.loginInfo.user_id;
    return { ssvUserId: uid ? String(uid) : undefined, ssvCustomData: customData || undefined };
};

// 미리 불러 둔 광고(한 장). 같은 사용자·용도일 때만 재사용한다.
let pending = null;   // { key, promise }
/** 광고를 미리 불러 둔다(누를 때 덮개가 짧게 끝나도록). 목업·웹은 아무것도 안 한다. */
export function preloadRewardedAd(customData) {
    if (!isNativeAdsEnabled()) return Promise.resolve(false);
    const opts = ssvOpts(customData);
    const key = JSON.stringify(opts);
    if (pending?.key === key) return pending.promise;
    const promise = loadRewardedAd(opts).then((ok) => {
        if (!ok && pending?.promise === promise) pending = null;   // 실패·시간 초과는 다음에 새로 받는다
        return ok;
    });
    pending = { key, promise };
    return promise;
}

let running = false;
/**
 * 보상형 광고 한 번. 덮개를 열고, 끝나면 닫는다.
 * @param {{ customData?: string }} [o]  SSV customData(서버는 지금 쓰지 않는다 — 기록용)
 * @returns {Promise<'rewarded'|'dismissed'|'failed'|'unavailable'|'busy'>}
 *   failed 는 불러오기 실패·시간 초과(10초)·재생 실패를 모두 포함한다.
 */
export async function runRewardedAd({ customData } = {}) {
    if (!rewardedAdSupported()) return 'unavailable';
    if (running) return 'busy';
    running = true;
    rewardedAdState.phase = 'loading';
    try {
        if (useMock()) return await runMock();
        const ok = await preloadRewardedAd(customData);
        pending = null;   // 한 번 보여주면 소진된다
        if (!ok) return 'failed';
        rewardedAdState.phase = 'showing';
        return await showRewardedAd();
    } catch (e) {
        console.warn('[rewarded] 실행 실패:', e?.message ?? e);
        return 'failed';
    } finally {
        running = false;
        rewardedAdState.phase = null;
        rewardedAdState.mock = false;
    }
}

// 목업: 0.8초 불러오는 척 → 가짜 광고(덮개 안 버튼)에서 결과를 고른다.
async function runMock() {
    await wait(800);
    rewardedAdState.phase = 'showing';
    rewardedAdState.mock = true;
    const result = await new Promise((resolve) => { mockAnswer = resolve; });
    mockAnswer = null;
    rewardedAdState.mock = false;
    if (result === 'rewarded' && assUserSession().user.accessToken) {
        // 서버 SSV 흉내: 꿀은 서버(목업)에 쌓이고, 화면은 요약을 다시 받아야 안다
        await aibeesApi.post('/api/v1/honey/mock-ad', {}).catch(() => null);
    }
    return result;
}

/** 목업 가짜 광고의 버튼이 부른다. */
export const answerMockAd = (result) => { mockAnswer?.(result); };
