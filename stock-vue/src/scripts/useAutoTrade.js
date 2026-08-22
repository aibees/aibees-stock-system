/**
 * 자동매매(AutoTrade) 공통 API 래퍼
 *  - 화면 3종(ModeSetting / LimitOrder / RunStatus)에서 공유
 *
 * ⚠ USE_MOCK
 *  모드 설정/운용 상태/이력은 이 저장소 밖(ROOT 서버, VITE_SERVER_URL)이 구현할
 *  예정이라 아직 mock 이다. API 가 준비되면 아래 상수만 false 로 바꾸면 된다.
 *
 * ⚠ 매도 수기등록(fetchHoldings/fetchManualSells/addManualSell/cancelManualSell)만은
 *  예외다. 이 기능은 이 저장소(py-stock-batch, app/trade_worker)에 이미 완전히
 *  구현돼 있어서 ROOT 서버를 기다릴 이유가 없다(2026-08-21) — USE_MOCK 값과
 *  무관하게 항상 실제 서버(batchApi → py-stock-batch)를 호출한다.
 */
import aibeesApi, { batchApi } from './aibeesApi.js';
import { assUserSession } from './stores/user-stores.js';
import * as mock from './autoTradeMock.js';

export const USE_MOCK = true;   // TODO: 백엔드 연동 후 false (모드/상태/이력 전용)

const BASE = '/api/v1/auto-trade';

/* 매도 수기등록은 py-stock-batch(app/flask_app/router/router_auto_trade.py)가
 * 직접 처리한다 — 이 앱 Flask 에는 JWT 인증 미들웨어가 없어(job_bp 포함 기존
 * 라우트 전부 무인증) user_id 를 프런트가 세션에서 직접 실어보낸다. */
const currentUserId = () => {
    const { user } = assUserSession();
    const uid = user?.loginInfo?.user_id;
    return uid ? Number(uid) : null;
};

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

/* ── 매도 수기등록 (모드 무관, 구 'M4/M3 지정가 감시' 폐기 후 대체)
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
    const user_id = currentUserId();
    if (!user_id) return [];   // 로그인 세션 없음 — 화면은 빈 목록으로 표시됨
    const { data } = await batchApi.get(`${BASE}/holdings`, { params: { user_id } });
    return data.data ?? [];
};

export const fetchManualSells = async () => {
    const user_id = currentUserId();
    if (!user_id) return [];   // 로그인 세션 없음 — 화면은 "미등록"으로 표시됨
    const { data } = await batchApi.get(`${BASE}/manual-sell`, { params: { user_id } });
    return data.data ?? [];
};

export const addManualSell = async (payload) => {
    const user_id = currentUserId();
    if (!user_id) throw new Error('로그인 세션이 없습니다.');
    const { data } = await batchApi.post(`${BASE}/manual-sell`, { ...payload, user_id });
    return data.data ?? {};
};

export const cancelManualSell = async (manual_sell_id) => {
    const user_id = currentUserId();
    if (!user_id) throw new Error('로그인 세션이 없습니다.');
    if (!manual_sell_id) throw new Error('취소할 등록 건을 찾을 수 없습니다.');
    await batchApi.post(`${BASE}/manual-sell/cancel`, { user_id, manual_sell_id });
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

export const MANUAL_SELL_STATE_LABEL = {
    ARMED: '지정가 감시 중',
    DONE: '매도 완료',
    CANCELLED: '취소됨',
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
