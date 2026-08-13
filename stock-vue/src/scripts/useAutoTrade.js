/**
 * 자동매매(AutoTrade) 공통 API 래퍼
 *  - 화면 3종(ModeSetting / LimitOrder / RunStatus)에서 공유
 *
 * ⚠ USE_MOCK
 *  백엔드 API 구현 전까지 화면 확인용 mock 데이터를 사용한다.
 *  API 가 준비되면 아래 상수만 false 로 바꾸면 실제 서버 호출로 전환된다.
 */
import aibeesApi from './aibeesApi.js';
import * as mock from './autoTradeMock.js';

export const USE_MOCK = true;   // TODO: 백엔드 연동 후 false

const BASE = '/api/v1/auto-trade';

/* ── 모드 마스터 ── */
export const fetchModes = async () => {
    if (USE_MOCK) return mock.mockFetchModes();
    const { data } = await aibeesApi.get(`${BASE}/modes`);
    return data.data ?? [];
};

/* ── 운용 상태 ── */
export const fetchState = async () => {
    if (USE_MOCK) return mock.mockFetchState();
    const { data } = await aibeesApi.get(`${BASE}/state`);
    return data.data ?? null;
};

/**
 * 모드 변경 요청
 * @returns {{applied:'NOW'|'RESERVED', run_state:string, message:string}}
 */
export const saveState = async (mode_code, config) => {
    if (USE_MOCK) return mock.mockSaveState(mode_code, config);
    const { data } = await aibeesApi.put(`${BASE}/state`, { mode_code, config });
    return data.data ?? {};
};

export const cancelPending = async () => {
    if (USE_MOCK) return mock.mockCancelPending();
    const { data } = await aibeesApi.delete(`${BASE}/state/pending`);
    return data.data ?? {};
};

export const setPower = async (enabled) => {
    if (USE_MOCK) return mock.mockSetPower(enabled);
    const { data } = await aibeesApi.post(`${BASE}/power`, { enabled });
    return data.data ?? {};
};

/* ── 지정가 예약 (M3) ── */
export const fetchLimitOrder = async () => {
    if (USE_MOCK) return mock.mockFetchLimitOrder();
    const { data } = await aibeesApi.get(`${BASE}/limit-order`);
    return data.data ?? null;
};

export const saveLimitOrder = async (payload) => {
    if (USE_MOCK) return mock.mockSaveLimitOrder(payload);
    const { data } = await aibeesApi.put(`${BASE}/limit-order`, payload);
    return data.data ?? {};
};

export const removeLimitOrder = async () => {
    if (USE_MOCK) return mock.mockRemoveLimitOrder();
    await aibeesApi.delete(`${BASE}/limit-order`);
};

/* ── 변경 이력 ── */
export const fetchHistory = async (limit = 30) => {
    if (USE_MOCK) return mock.mockFetchHistory(limit);
    const { data } = await aibeesApi.get(`${BASE}/history`, { params: { limit } });
    return data.data ?? [];
};

/* ── 종목 검색 (기존 API 재사용) ── */
export const searchStocks = async (searchTxt) => {
    if (USE_MOCK) return mock.mockSearchStocks(searchTxt);
    const { data } = await aibeesApi.get('/api/v1/stocks/search', { params: { searchTxt } });
    const list = data.data ?? [];
    list.forEach(d => { d.type = d.stock_type_yf === 'KQ' ? '코스닥' : '코스피'; });
    return list;
};

/* ── [MOCK 전용] 데모 조작 ── */
export const simulateSell = async () => (USE_MOCK ? mock.mockSimulateSell() : null);
export const resetPosition = async () => (USE_MOCK ? mock.mockResetPosition() : null);

/* ── 표시 헬퍼 ── */
export const RUN_STATE_LABEL = {
    IDLE: '정지',
    ARMED: '매수 대기',
    HOLDING: '보유 중',
    SWITCH_PENDING: '전환 예약됨',
};

export const ORDER_STATE_LABEL = {
    WAIT_BUY: '매수가 감시 중',
    BOUGHT: '매수 체결 · 매도가 감시 중',
    DONE: '매도 완료',
    STOPPED: '손절 종료',
};

export const formatNumber = (v) =>
    (v === null || v === undefined || v === '') ? '-' : Number(v).toLocaleString();

export const formatDateTime = (v) => {
    if (!v) return '-';
    const d = new Date(v);
    if (Number.isNaN(d.getTime())) return String(v);
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}.${p(d.getMonth() + 1)}.${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};
