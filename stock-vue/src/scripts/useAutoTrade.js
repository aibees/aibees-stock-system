/**
 * 자동매매(AutoTrade) 공통 API 래퍼
 *  - 화면 3종(ModeSetting / LimitOrder / RunStatus)에서 공유
 *
 * 모드/상태/이력: ROOT 서버(py-naver-stock-theme router_auto_trade.py, WORKER_USER 전용).
 *  전환은 항상 즉시 적용 — worker 에 보유분 청산 후 승계(pending) 로직이 없어 예약/전원 API 는 두지 않는다.
 *  USE_MOCK=true 로 되돌리면 autoTradeMock 데모 데이터로 화면만 볼 수 있다.
 *
 * 매도 수기등록(fetchHoldings/fetchManualSells/addManualSell/cancelManualSell)도 ROOT 서버가 맡는다
 *  (router_manual_sell.py, JWT + WORKER_USER). USE_MOCK 값과 무관하게 항상 실제 서버를 호출한다.
 */
import aibeesApi from './aibeesApi.js';
import * as mock from './autoTradeMock.js';

export const USE_MOCK = false;

/* 모드·상태·이력 — ROOT 서버(py-naver-stock-theme). */
const BASE = '/api/v1/auto-trade';

/* 매도 수기등록 — 등록된 지정가는 실제 매도로 이어지므로 JWT 로 사용자를 확인하는 ROOT 서버로 보낸다. */
const SELL_BASE = `${BASE}/manual-sell`;

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
 * 운용모드 즉시 전환 (M0 = 매매정지)
 * @returns {{applied:'NOW'|'NONE', active_mode:string, message:string}}
 */
export const saveState = async (mode_code) => {
    if (USE_MOCK) return mock.mockSaveState(mode_code, {});
    const { data } = await aibeesApi.put(`${BASE}/state`, { mode_code });
    return data.data ?? {};
};

/* ── 매도 수기등록 (모드 무관, 지정가 감시는 운용모드가 아님)
 *   보유 종목에 지정 매도가를 걸어두면, 활성 운용모드가 무엇이든 그 모드의
 *   자동 매도 rule 대신 이 가격 도달 여부로 worker 가 대신 체결한다.
 *   백엔드: app/trade_worker (trade_worker_manual_sell, sql/08_manual_sell_order_ddl.sql
 *   + 09_manual_sell_multi_ddl.sql).
 *   spec: py-stock-batch/spec_docs/docs_worker_mode_runtime_spec.md §11
 *
 *   2026-08-21 다건화: 종목당 1건(단일 슬롯)이던 제약을 풀어 종목당 여러 지정가
 *   (사다리 매도)와 여러 종목 동시 등록을 허용했다. 그래서 조회는 이제 "지금
 *   등록된 것 1건"이 아니라 유저의 등록 전체 목록(fetchManualSells)이고, 등록은
 *   항상 새 티어 생성(addManualSell)이며, 취소는 특정 티어 하나만 id 로 지정한다
 *   (cancelManualSell). 등록 가능 조건은 계좌 실보유(user_holdings)뿐이다 —
 *   worker 가 직접 매수한 종목(trade_worker_position)으로 좁히지 않는다.
 */
export const fetchHoldings = async () => {
    const { data } = await aibeesApi.get(`${SELL_BASE}/holdings`);
    return data.data ?? [];
};

export const fetchManualSells = async () => {
    const { data } = await aibeesApi.get(`${SELL_BASE}/orders`);
    return data.data ?? [];
};

export const addManualSell = async (payload) => {
    const { data } = await aibeesApi.post(`${SELL_BASE}/orders`, payload);
    return data.data ?? {};
};

export const cancelManualSell = async (manual_sell_id) => {
    if (!manual_sell_id) throw new Error('취소할 등록 건을 찾을 수 없습니다.');
    await aibeesApi.post(`${SELL_BASE}/orders/cancel`, { manual_sell_id });
};

/* 지갑 "지금 팔기" — 보유 전량 시장가 매도 요청(정규장만). 실제 돈이 움직이는 요청이라 JWT 로 사용자를 확인하는
 *  ROOT 서버로 보낸다. 서버가 즉시 도달하는 손절 티어를 등록하고, worker 가 다음 재적재(최대 약 1분) 후 판다. */
export const sellNow = async (stock_code) => {
    const { data } = await aibeesApi.post(`${BASE}/sell-now`, { stock_code });
    return data.data ?? {};
};

/* ── 수동 매수 ──
 *  ROOT 서버(router_manual_buy.py, JWT + WORKER_USER)에 요청을 저장하면 worker 가 바로 주문한다.
 *  client_key 가 같은 재전송은 같은 주문을 돌려준다(주문 1건). */
const MANUAL_BUY_BASE = `${BASE}/manual-buy`;

export const fetchManualBuys = async (limit = 30) => {
    const { data } = await aibeesApi.get(MANUAL_BUY_BASE, { params: { limit } });
    return data.data ?? [];
};

export const placeManualBuy = async (payload) => {
    const { data } = await aibeesApi.post(MANUAL_BUY_BASE, payload);
    return data.data ?? {};
};

export const cancelManualBuy = async (id) => {
    const { data } = await aibeesApi.post(`${MANUAL_BUY_BASE}/${id}/cancel`);
    return data.data ?? {};
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

/**
 * 에러 메시지 추출 — 화면 3종이 공유한다.
 *
 * aibeesApi/batchApi 의 response interceptor 는 `error.response?.data ?? error` 로
 * **reject 한다**(aibeesApi.js). 즉 호출부가 받는 값은 axios 에러가 아니라 서버
 * 본문 `{ success:false, error:{ message } }` 그 자체다. 그런데 화면들은
 * `e.response.data.error.message` 를 보고 있어서 **항상 undefined → 기본 문구**로
 * 떨어졌다. 그래서 403("자동매매 사용자만 이용할 수 있습니다.") 같은 서버 메시지가
 * 한 번도 화면에 안 나왔다. 두 모양을 모두 받는다 — 404 처럼 본문이 HTML 인
 * 경우에는 꺼낼 게 없으므로 fallback 을 쓴다.
 */
export const apiErrorMessage = (e, fallback) =>
    e?.error?.message            // interceptor 가 벗겨서 준 서버 본문
    || e?.response?.data?.error?.message   // 혹시 raw axios 에러로 온 경우
    || e?.response?.data?.message
    || fallback;

/* ── 표시 헬퍼 ── */
export const RUN_STATE_LABEL = {
    IDLE: '정지',
    ARMED: '매수 대기',
    HOLDING: '보유 중',
    SWITCH_PENDING: '전환 예약됨',
};

export const MANUAL_SELL_STATE_LABEL = {
    ARMED: '지정가 감시 중',
    DONE: '매도 완료',
    CANCELLED: '취소됨',
};

export const MANUAL_BUY_STATE_LABEL = {
    REQUESTED: '주문 대기',
    ORDERING: '주문 중',
    OPEN: '체결 대기',
    FILLED: '체결 완료',
    CANCELLED: '취소됨',
    REJECTED: '주문 거부',
    EXPIRED: '만료됨',
    UNKNOWN: '확인 필요',
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
