/**
 * 주식분석 유의사항 동의 — 내비(하단 탭·상단 메뉴)에서 주식분석을 처음 누를 때 한 번 받는다(2026-11-22).
 *
 * 먼저 이 기기(localStorage 'yb-stock-notice' = {version, agreedAt, owner})에 두고, 로그인 중이면 계정에도 남긴다
 * (기존 동의 표 user_consent·user_consent_history 에 consent_type 'STOCK_NOTICE', API POST /api/v1/training/stock-notice).
 *   owner : 동의를 계정에 올린 user_id. null 이면 로그인 전 동의 → 다음에 로그인하는 계정으로 올린다.
 * 로그인할 때 맞추기는 training-store 의 syncWithAccount 가 학습 기록과 같은 응답으로 한다(applyAccountStockNotice).
 *   계정에 현재 버전 동의가 있으면 기기도 동의로, 없으면 기기의 로그인 전 동의를 올린다.
 *   기기 동의가 다른 계정 것이면 이 계정에서는 다시 묻는다.
 * 문구를 크게 바꿔 다시 받아야 하면 VERSION 을 올린다 — 저장된 버전과 다르면 다시 묻는다.
 * 저장소를 못 쓰면 이번 실행 동안만 기억한다.
 */
import { reactive } from 'vue';
import aibeesApi from './aibeesApi.js';
import { assUserSession } from './stores/user-stores.js';

const API_PATH = '/api/v1/training/stock-notice';

const STORAGE_KEY = 'yb-stock-notice';
export const STOCK_NOTICE_VERSION = 1;

/** 유의사항 항목. 순서 그대로 보여 준다. */
export const STOCK_NOTICE_ITEMS = [
    {
        title: '참고 자료이며 투자 권유가 아닙니다',
        body: '양봉상회가 보여 드리는 종목·지표·분석은 공부를 돕기 위한 참고 자료입니다. 특정 종목을 사거나 팔라는 권유가 아니며, 투자 판단과 그 결과의 책임은 본인에게 있습니다.',
    },
    {
        title: '지표 값은 실제와 다를 수 있습니다',
        body: '보조지표는 양봉상회가 받은 시세로 직접 계산한 값이라 증권사·포털의 값과 오차 범위 안에서 다를 수 있고, 시세가 늦게 반영될 수도 있습니다.',
    },
    {
        title: '스스로 차트를 읽는 힘을 기르는 보조 학습입니다',
        body: '주식분석 메뉴는 차트를 직접 분석하는 역량을 키우도록 돕는 학습 도구입니다. 화면의 결과를 그대로 따르기보다 왜 그런 결과가 나왔는지 함께 살펴보세요.',
    },
    {
        title: '본인 수준에 맞게 투자하세요',
        body: '주식은 원금 손실이 날 수 있습니다. 감당할 수 있는 금액 안에서, 이해한 만큼만 투자하시길 권합니다.',
    },
    {
        title: '일부 종목은 검색되지 않을 수 있습니다',
        body: '투자하기에 적합하지 않아 보이는 종목(회사)은 양봉상회가 자체 기준으로 제외해 두어, 검색해도 나오지 않을 수 있습니다.',
    },
];

let memory = null;   // 저장소를 못 쓸 때의 대신

const readSaved = () => {
    try {
        const v = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
        return v && typeof v === 'object' ? v : memory;
    } catch {
        return memory;
    }
};
const writeSaved = (v) => {
    memory = v;
    try {
        if (v) localStorage.setItem(STORAGE_KEY, JSON.stringify(v));
        else localStorage.removeItem(STORAGE_KEY);
    } catch { /* 저장 실패 — 이번 실행 동안만 기억한다 */ }
};

const currentUserId = () => {
    const s = assUserSession();
    return s.user.accessToken ? (s.user.loginInfo?.user_id || null) : null;
};

/** 이 기기(지금 로그인한 계정 기준)에서 현재 버전에 동의했는가. 다른 계정이 한 동의는 치지 않는다. */
export const isStockNoticeAgreed = () => {
    const v = readSaved();
    if (Number(v?.version) !== STOCK_NOTICE_VERSION) return false;
    const uid = currentUserId();
    return v.owner == null || !uid || v.owner === uid;
};

const pushToAccount = async (uid) => {
    await aibeesApi.post(API_PATH, { version: STOCK_NOTICE_VERSION });
    writeSaved({ ...readSaved(), owner: uid });
};

/** 동의를 기록한다. 로그인 중이면 계정에도 올린다(실패해도 기기에는 남는다). */
export const markStockNoticeAgreed = () => {
    const uid = currentUserId();
    writeSaved({ version: STOCK_NOTICE_VERSION, agreedAt: Date.now(), owner: null });
    if (uid) pushToAccount(uid).catch(e => console.warn('[stock-notice] 계정 저장 실패 — 기기에는 저장됨', e?.message ?? e));
};

/**
 * 로그인할 때 계정 동의(GET /api/v1/training/progress 의 stock_notice)와 맞춘다. training-store 가 부른다.
 *   server : {version, agreed_at} | null
 */
export const applyAccountStockNotice = async (uid, server) => {
    if (Number(server?.version) === STOCK_NOTICE_VERSION) {
        writeSaved({ version: STOCK_NOTICE_VERSION, agreedAt: server.agreed_at ?? Date.now(), owner: uid });
        return;
    }
    const v = readSaved();
    const localCurrent = Number(v?.version) === STOCK_NOTICE_VERSION;
    if (localCurrent && (v.owner == null || v.owner === uid)) {
        await pushToAccount(uid);   // 로그인 전에 한 동의(또는 올리다 실패한 동의)를 이 계정으로 올린다
    } else if (localCurrent) {
        writeSaved(null);           // 다른 계정의 동의 — 이 계정에서는 다시 묻는다
    }
};

/**
 * 팝업 상태(앱 전체에서 하나). 내비가 open(경로)로 띄우고, 확인하면 그 경로로 간다.
 * StockNoticeDialog.vue 가 이 상태를 그린다.
 */
export const stockNotice = reactive({ show: false, path: '' });

/** 동의했으면 true(바로 이동해도 됨), 아니면 팝업을 띄우고 false. */
export const requireStockNotice = (path) => {
    if (isStockNoticeAgreed()) return true;
    stockNotice.path = path;
    stockNotice.show = true;
    return false;
};
