/**
 * [MOCK] 자동매매 화면용 임시 데이터 레이어
 *  - 백엔드 API 구현 전 화면 동작 확인용. 인메모리라 새로고침하면 초기화된다.
 *  - 실제 API 연결 시 useAutoTrade.js 의 USE_MOCK 을 false 로 바꾸면 이 파일은 안 쓰인다.
 */

const delay = (ms = 260) => new Promise(r => setTimeout(r, ms));
const now = () => new Date().toISOString();
const clone = (o) => JSON.parse(JSON.stringify(o ?? null));

/* ── 모드 마스터 ── */
const MODES = [
    {
        mode_code: 'M0', mode_name: '추천 1순위 자동매매',
        mode_desc: '매일 저녁 8시 배치가 뽑은 추천 종목 중 <b>1순위 종목을 익일 전량 매수</b>합니다.<br/>매도는 기존 S1 전략(손절·익절·트레일링·타임스탑)을 따릅니다.',
        need_stock: 'N', need_pair: 'N', need_price: 'N', sort_order: 1, enabled_flag: 'Y',
    },
    {
        mode_code: 'M1', mode_name: '단일 종목 고정',
        mode_desc: '지정한 <b>종목 1개만</b> 반복 매매합니다. ETF·개별주 모두 가능.<br/>진입 규칙은 즉시매수 / 신호대기 중 선택합니다.',
        need_stock: 'Y', need_pair: 'N', need_price: 'N', sort_order: 2, enabled_flag: 'Y',
    },
    {
        mode_code: 'M2', mode_name: 'KOSPI100 ETF ↔ 인버스 교대',
        mode_desc: 'KOSPI 지수 추세를 판단해 <b>정방향 ETF</b> 또는 <b>인버스 ETF</b> 한쪽만 보유합니다.<br/>반대 신호가 나오면 청산 후 반대편으로 전환합니다.',
        need_stock: 'N', need_pair: 'Y', need_price: 'N', sort_order: 3, enabled_flag: 'Y',
    },
    // 구 'M3 지정가 감시 매매'(설계 문서 기준 M4)는 폐기됐다.
    // 매도가 도달 시 자동 체결하는 기능 자체는 없어지지 않았고, 모드 선택과
    // 무관하게 '매도 수기 등록' 화면(LimitOrder.vue)으로 옮겨졌다 — 위 모드
    // 중 무엇을 쓰든 보유 종목에 지정가를 걸어두면 그 종목만 자동 rule 대신
    // 지정가로 감시된다. spec_docs/docs_worker_mode_runtime_spec.md §6·§11 참고.
];

/* ── 운용 상태 (보유 중 시나리오로 시작) ── */
const db = {
    state: {
        enabled_flag: 'Y',
        run_state: 'HOLDING',
        active_mode: 'M0',
        active_config: {},
        active_from: '2026-08-04T09:03:00',
        pending_mode: null,
        pending_config: null,
        pending_at: null,
        last_tick_at: '2026-08-11T14:52:10',
        last_message: 'HOLD · 수익률 +3.21% · 트레일링 라인 71,480 미도달 (보유 5봉)',
        position: {
            stock_code: '005930', stock_name: '삼성전자', trade_mode: 'M0',
            entry_price: 71200, qty: 14, profit_pct: '+3.21%',
            stop_price: 67640, target_price: 92560, trail_line: 71480,
            bars_held: 5, sell_reason: null,
        },
    },
    // 매도 수기등록 — 보유 종목 1개에 지정 매도가를 걸어두면, 현재 활성 모드가
    // 무엇이든 그 모드의 자동 매도 rule(손절/익절/트레일링) 대신 이 가격 도달
    // 여부만으로 worker 가 대신 체결한다. 매수는 관여하지 않는다(기존 M4 처럼
    // 매수가를 함께 지정하지 않음 — 매수는 항상 활성 모드가 담당).
    // 백엔드 대응: app/trade_worker/repository.py get_active_manual_sells 등
    // (trade_worker_manual_sell, sql/08_manual_sell_order_ddl.sql).
    manualSell: {
        stock_code: '069500', stock_name: 'KODEX 200',
        sell_price: 41200, qty_ratio: 1,
        state: 'ARMED', enabled_flag: 'Y', memo: '목표가 도달 시 전량 매도',
        filled_price: null, filled_qty: null, filled_at: null,
    },
    history: [
        { log_id: 3, action_type: 'APPLY_NOW', from_mode: null, to_mode: 'M0', reason: '최초 설정', actor: 'USER', created_at: '2026-08-01T10:12:00' },
        { log_id: 2, action_type: 'START', from_mode: 'M0', to_mode: 'M0', reason: '자동매매 시작', actor: 'USER', created_at: '2026-08-01T10:12:20' },
        { log_id: 1, action_type: 'COMMIT', from_mode: 'M0', to_mode: 'M0', reason: '매도 체결 후 재무장', actor: 'WORKER', created_at: '2026-08-04T09:03:00' },
    ],
    seq: 4,
};

const MODE_NAME = Object.fromEntries(MODES.map(m => [m.mode_code, m.mode_name]));

const pushLog = (action_type, from_mode, to_mode, reason, actor = 'USER') => {
    db.history.unshift({
        log_id: db.seq++, action_type, from_mode, to_mode, reason, actor, created_at: now(),
    });
};

/* ── API 대응 함수 ── */
export const mockFetchModes = async () => { await delay(); return clone(MODES); };

export const mockFetchState = async () => { await delay(); return clone(db.state); };

export const mockSaveState = async (mode_code, config) => {
    await delay();
    const s = db.state;
    const holding = ['HOLDING', 'SWITCH_PENDING'].includes(s.run_state);

    if (holding) {
        s.pending_mode = mode_code;
        s.pending_config = clone(config);
        s.pending_at = now();
        s.run_state = 'SWITCH_PENDING';
        pushLog('RESERVED', s.active_mode, mode_code, '보유 중 전환 예약');
        return {
            applied: 'RESERVED',
            run_state: s.run_state,
            message: `보유 중인 ${s.position?.stock_name ?? '종목'} 매도 체결 후 '${MODE_NAME[mode_code]}' 로 자동 전환됩니다.`,
        };
    }

    const from = s.active_mode;
    s.active_mode = mode_code;
    s.active_config = clone(config);
    s.active_from = now();
    s.pending_mode = null;
    s.pending_config = null;
    s.pending_at = null;
    s.run_state = s.enabled_flag === 'Y' ? 'ARMED' : 'IDLE';
    s.last_message = `'${MODE_NAME[mode_code]}' 적용 완료. 매수 조건 감시 대기 중.`;
    pushLog('APPLY_NOW', from, mode_code, '미보유 상태라 즉시 적용');
    return { applied: 'NOW', run_state: s.run_state, message: `'${MODE_NAME[mode_code]}' 로 즉시 적용되었습니다.` };
};

export const mockCancelPending = async () => {
    await delay();
    const s = db.state;
    pushLog('RESERVE_CANCEL', s.active_mode, s.pending_mode, '사용자 취소');
    s.pending_mode = null;
    s.pending_config = null;
    s.pending_at = null;
    s.run_state = s.position ? 'HOLDING' : (s.enabled_flag === 'Y' ? 'ARMED' : 'IDLE');
    return { run_state: s.run_state };
};

export const mockSetPower = async (enabled) => {
    await delay();
    const s = db.state;
    s.enabled_flag = enabled;
    if (enabled === 'N') {
        s.run_state = s.position ? 'HOLDING' : 'IDLE';
        s.last_message = '운용 정지. 신규 매수는 중단되고 보유 종목 매도 감시만 유지됩니다.';
    } else {
        s.run_state = s.position ? (s.pending_mode ? 'SWITCH_PENDING' : 'HOLDING') : 'ARMED';
        s.last_message = '운용 시작. 매수 조건 감시 중.';
    }
    pushLog(enabled === 'Y' ? 'START' : 'STOP', s.active_mode, s.active_mode, enabled === 'Y' ? '운용 시작' : '운용 정지');
    return { enabled_flag: s.enabled_flag, run_state: s.run_state };
};

export const mockFetchManualSell = async () => { await delay(); return clone(db.manualSell); };

export const mockSaveManualSell = async (payload) => {
    await delay();
    db.manualSell = { ...(db.manualSell ?? {}), ...clone(payload) };
    if (!db.manualSell.state) db.manualSell.state = 'ARMED';
    return clone(db.manualSell);
};

export const mockRemoveManualSell = async () => { await delay(); db.manualSell = null; };

export const mockFetchHistory = async (limit = 30) => { await delay(); return clone(db.history).slice(0, limit); };

export const mockSearchStocks = async (searchTxt) => {
    await delay(200);
    const pool = [
        { stock_code: '005930', stock_name: '삼성전자', stock_type_yf: 'KS' },
        { stock_code: '000660', stock_name: 'SK하이닉스', stock_type_yf: 'KS' },
        { stock_code: '069500', stock_name: 'KODEX 200', stock_type_yf: 'KS' },
        { stock_code: '229200', stock_name: 'KODEX 코스닥150', stock_type_yf: 'KS' },
        { stock_code: '114800', stock_name: 'KODEX 인버스', stock_type_yf: 'KS' },
        { stock_code: '252670', stock_name: 'KODEX 200선물인버스2X', stock_type_yf: 'KS' },
        { stock_code: '102110', stock_name: 'TIGER 200', stock_type_yf: 'KS' },
        { stock_code: '123310', stock_name: 'TIGER 인버스', stock_type_yf: 'KS' },
        { stock_code: '035720', stock_name: '카카오', stock_type_yf: 'KS' },
        { stock_code: '247540', stock_name: '에코프로비엠', stock_type_yf: 'KQ' },
    ];
    const kw = String(searchTxt ?? '').trim().toLowerCase();
    return pool
        .filter(s => s.stock_name.toLowerCase().includes(kw) || s.stock_code.includes(kw))
        .map(s => ({ ...s, type: s.stock_type_yf === 'KQ' ? '코스닥' : '코스피' }));
};

/* ── [MOCK 전용] 매도 체결 시뮬레이션 : pending → active 승계 흐름 확인용 ── */
export const mockSimulateSell = async () => {
    await delay();
    const s = db.state;
    if (!s.position) return { message: '보유 중인 포지션이 없습니다.' };

    const sold = s.position;
    s.position = null;
    pushLog('COMMIT', s.active_mode, s.pending_mode ?? s.active_mode,
        `${sold.stock_name} 매도 체결 (${sold.profit_pct})`, 'WORKER');

    if (s.pending_mode) {
        const from = s.active_mode;
        s.active_mode = s.pending_mode;
        s.active_config = clone(s.pending_config);
        s.active_from = now();
        s.pending_mode = null;
        s.pending_config = null;
        s.pending_at = null;
        s.run_state = s.enabled_flag === 'Y' ? 'ARMED' : 'IDLE';
        s.last_message = `${sold.stock_name} 매도 체결 → 예약된 '${MODE_NAME[s.active_mode]}' 로 전환 완료 (이전 ${MODE_NAME[from]}).`;
    } else {
        s.run_state = s.enabled_flag === 'Y' ? 'ARMED' : 'IDLE';
        s.last_message = `${sold.stock_name} 매도 체결. 다음 매수 조건 감시 대기.`;
    }
    s.last_tick_at = now();
    return { message: s.last_message };
};

/* ── [MOCK 전용] 초기 시나리오 되돌리기 ── */
export const mockResetPosition = async () => {
    await delay();
    db.state.position = {
        stock_code: '005930', stock_name: '삼성전자', trade_mode: db.state.active_mode,
        entry_price: 71200, qty: 14, profit_pct: '+3.21%',
        stop_price: 67640, target_price: 92560, trail_line: 71480,
        bars_held: 5, sell_reason: null,
    };
    db.state.run_state = db.state.pending_mode ? 'SWITCH_PENDING' : 'HOLDING';
    db.state.last_message = 'HOLD · 수익률 +3.21% · 트레일링 라인 71,480 미도달 (보유 5봉)';
    db.state.last_tick_at = now();
    return { run_state: db.state.run_state };
};
