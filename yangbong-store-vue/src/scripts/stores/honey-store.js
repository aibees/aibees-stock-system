/**
 * 꿀(포인트) 1단계 화면 상태. 기획: docs/points-plan.md · 서버: py-yangbong-api router_honey.py
 *
 * - 꿀은 로그인한 사용자만 모은다(서버가 계정에 쌓는다). 비로그인이면 available=false 로 꿀 영역에 로그인 안내만 보인다.
 * - 지급은 서버만 한다. 화면은 요청을 보내고, 서버가 돌려준 요약(summary)과 받은 양(gained)을 그대로 쓴다.
 * - 광고 꿀은 AdMob 이 서버에 시청 완료를 알려 준 뒤에 쌓인다(서버 측 확인). 그래서 광고를 다 보면
 *   요약을 몇 번 다시 불러 광고 횟수가 늘었는지 보고, 늘었으면 받은 꿀을 보여준다.
 * - 받은 꿀은 pop 에 넣는다 → HoneyPop.vue 가 꿀단지 연출 + '꿀 +30' 을 띄운다.
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores.js';
import { MOCK_ENABLED } from '@scripts/mock/mockApi.js';
import { isNativeAdsEnabled, loadRewardedAd, showRewardedAd } from '@scripts/useAdMob.js';
import { ensureAccess } from '@scripts/useAccess.js';

const API = '/api/v1/honey';
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

export const HONEY_KIND_LABEL = {
    ATTEND: '출석 체크', STREAK: '7일 연속 출석', START: '처음 시작하기', LESSON: '수업 완료',
    QUIZ: '오늘의 한 문제', AD: '광고 보고 받기', SPEND_DAY_PASS: '프리미엄 하루 이용권',
    INVITE: '친구 초대', INVITED: '초대 코드 등록',
};

export const useHoneyStore = defineStore('honey', () => {
    const summary = ref(null);
    const loading = ref(false);
    const failed = ref(false);
    const pop = ref(null);          // { amount, key } — 받은 꿀 연출
    const busy = ref(false);
    const invite = ref(null);        // 친구 초대(2단계) 현황

    const loggedIn = () => !!assUserSession().user.accessToken;
    const available = computed(() => !!summary.value);
    const balance = computed(() => summary.value?.balance ?? 0);
    const todayEarned = computed(() => summary.value?.today?.earned ?? 0);
    const todayTarget = computed(() => summary.value?.today?.target ?? 360);
    // 오늘 더 모을 수 있는 꿀(광고 남은 횟수 + 출석·문제). 수업은 단계가 남아 있으면 '하나쯤' 더한다.
    const todayLeft = computed(() => {
        const s = summary.value;
        if (!s) return 0;
        const adLeft = s.ad.count >= s.ad.max ? 0 : adRemainingTotal(s.ad.count, s.ad.max);
        return adLeft + (s.attend.done ? 0 : s.attend.amount) + (s.quiz.done ? 0 : s.quiz.amount);
    });
    const allDone = computed(() => !!summary.value && todayLeft.value === 0);
    // 광고는 앱(네이티브)에서만 꿀이 쌓인다. 목업 모드는 화면 확인용으로 흉내 낸다.
    const adSupported = computed(() => isNativeAdsEnabled() || MOCK_ENABLED);
    const dayPassUntil = computed(() => summary.value?.dayPass?.until ?? null);

    const show = (amount) => { if (amount > 0) pop.value = { amount, key: Date.now() }; };

    const load = async () => {
        if (!loggedIn()) { summary.value = null; return null; }
        loading.value = true;
        try {
            const { data } = await aibeesApi.get(API);
            summary.value = data?.data ?? null;
            failed.value = false;
        } catch (e) {
            failed.value = true;   // 꿀 표가 없거나 서버 오류 — 꿀 영역을 숨긴다
            summary.value = null;
        } finally {
            loading.value = false;
        }
        return summary.value;
    };

    const post = async (path, body, config) => {
        const { data } = await aibeesApi.post(API + path, body ?? {}, config);
        const d = data?.data ?? {};
        if (d.summary) summary.value = d.summary;
        show(d.gained ?? 0);
        return d;
    };

    const attend = () => post('/attend').catch(() => null);
    const quizCorrect = () => (loggedIn() ? post('/quiz', { correct: true }).catch(() => null) : null);
    const startDone = () => (loggedIn() ? post('/start').catch(() => null) : null);

    /** 학습 기록 API 가 돌려준 수업 꿀을 반영한다(training-store 가 부른다). */
    const lessonGained = (amount) => { if (amount > 0) { show(amount); load(); } };

    /** 프리미엄 하루 이용권. 성공하면 권한을 다시 받아 프리미엄 단계가 바로 열린다. */
    const buyDayPass = async () => {
        busy.value = true;
        try {
            await post('/spend', { item: 'DAY_PASS' }, { silentError: true });
            await ensureAccess(true);
            return true;
        } catch (e) {
            return e?.error?.message || e?.response?.data?.error?.message || '꿀을 쓰지 못했어요.';
        } finally {
            busy.value = false;
        }
    };

    /**
     * 광고 보고 꿀 받기. 결과: 'rewarded' | 'dismissed' | 'failed' | 'unavailable'
     * 앱: 광고를 끝까지 보면 서버가 AdMob 확인을 받아 꿀을 넣는다 → 요약을 다시 불러 늘었는지 본다.
     */
    const watchAd = async () => {
        if (!adSupported.value) return 'unavailable';
        const s = summary.value;
        if (s && s.ad.count >= s.ad.max) return 'unavailable';
        busy.value = true;
        try {
            if (MOCK_ENABLED && !isNativeAdsEnabled()) {
                await wait(600);
                await post('/mock-ad');
                return 'rewarded';
            }
            const uid = assUserSession().user.loginInfo.user_id;
            if (!(await loadRewardedAd({ ssvUserId: uid ? String(uid) : undefined }))) return 'failed';
            const result = await showRewardedAd();
            if (result === 'rewarded' && uid) await collectAdReward();
            return result;
        } finally {
            busy.value = false;
        }
    };

    // AdMob → 서버 알림은 보통 몇 초 안에 온다. 광고 횟수가 늘 때까지 잠깐 다시 불러 본다.
    const collectAdReward = async () => {
        const before = summary.value?.ad?.count ?? 0;
        const beforeBal = summary.value?.balance ?? 0;
        for (let i = 0; i < 6; i++) {
            await wait(1500);
            const s = await load();
            if (s && s.ad.count > before) { show(s.balance - beforeBal); return; }
        }
    };

    const ledger = async (before) => {
        const { data } = await aibeesApi.get(API + '/ledger', { params: { before, limit: 50 } });
        return Array.isArray(data?.data) ? data.data : [];
    };

    // ── 친구 초대(2단계) ──
    // 같은 기기 반복 가입을 막는 기기 표시: 이 기기 저장소의 무작위 값(앱을 지우면 바뀐다)
    const deviceId = () => {
        try {
            let id = localStorage.getItem('yb-device-id');
            if (!id) { id = (crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`); localStorage.setItem('yb-device-id', id); }
            return id;
        } catch { return null; }
    };
    const loadInvite = async () => {
        if (!loggedIn()) { invite.value = null; return null; }
        try {
            const { data } = await aibeesApi.get(API + '/invite');
            invite.value = data?.data ?? null;
        } catch { invite.value = null; }
        return invite.value;
    };
    /** 친구 코드 넣기. 성공하면 true, 아니면 화면에 보일 이유 */
    const redeemInvite = async (code) => {
        busy.value = true;
        try {
            const { data } = await aibeesApi.post(API + '/invite/redeem', { code, deviceId: deviceId() }, { silentError: true });
            const d = data?.data ?? {};
            if (d.invite) invite.value = d.invite;
            if (d.summary) summary.value = d.summary;
            show(d.gained ?? 0);
            return true;
        } catch (e) {
            return e?.error?.message || e?.response?.data?.error?.message || '초대 코드를 등록하지 못했어요.';
        } finally {
            busy.value = false;
        }
    };

    const reset = () => { summary.value = null; invite.value = null; };

    return {
        summary, loading, failed, pop, busy, available, balance, todayEarned, todayTarget, todayLeft, allDone,
        adSupported, dayPassUntil, load, attend, quizCorrect, startDone, lessonGained, buyDayPass, watchAd, ledger, reset,
        afterGateAd: collectAdReward, invite, loadInvite, redeemInvite,
    };
});

/** 오늘 남은 광고를 다 보면 받는 꿀 합(1·2·3번째 20·30·40, 그 뒤 30). 서버 honey_service.ad_reward 와 같아야 한다. */
export const adReward = (countBefore) => [20, 30, 40][countBefore] ?? 30;
const adRemainingTotal = (count, max) => {
    let sum = 0;
    for (let i = count; i < max; i++) sum += adReward(i);
    return sum;
};
