<template>
    <div id="trade-log">
        <Headers :prop_title="title" />

        <div class="contents">

            <!-- ── 상단 타이틀 ── -->
            <section class="head-desc">
                <div class="head-left">
                    <h2>거래 내역</h2>
                    <p class="sub-text">체결 내역 · worker 매매 이력 · 운영 로그를 조회합니다 (최신순)</p>
                </div>
                <div class="head-right">
                    <button class="btn-refresh" @click="reloadCurrent">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M23 4v6h-6" />
                            <path d="M1 20v-6h6" />
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10" />
                            <path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14" />
                        </svg>
                        새로고침
                    </button>
                </div>
            </section>

            <!-- ── 탭 ── -->
            <nav class="tab-nav">
                <button v-for="t in tabs" :key="t.key" :class="['tab-btn', { active: activeTab === t.key }]"
                    @click="switchTab(t.key)">
                    {{ t.label }}
                </button>
            </nav>

            <!-- ══ 탭1: 거래 체결 (trade-logs) ══ -->
            <div v-show="activeTab === 'trade'">
                <section class="filter-bar">
                    <div class="filter-group">
                        <span class="filter-label">구분</span>
                        <div class="chip-group">
                            <button v-for="o in actionOptions" :key="o.value"
                                :class="['filter-chip', { active: tradeFilter.action === o.value }]"
                                @click="setTradeFilter('action', o.value)">{{ o.label }}</button>
                        </div>
                    </div>
                    <div class="filter-group">
                        <span class="filter-label">종목코드</span>
                        <input class="filter-input" v-model.trim="tradeFilter.stock_code" placeholder="예) 005930"
                            @keyup.enter="applyTradeFilter" />
                    </div>
                    <div class="filter-group">
                        <span class="filter-label">기간</span>
                        <input class="filter-input date" type="date" v-model="tradeFilter.from" />
                        <span class="tilde">~</span>
                        <input class="filter-input date" type="date" v-model="tradeFilter.to" />
                    </div>
                    <button class="btn-apply" @click="applyTradeFilter">조회</button>
                </section>

                <section class="table-section">
                    <div v-if="trade.loading" class="loader-rows"><div v-for="n in 6" :key="n" class="skeleton-row"></div></div>
                    <table v-else class="grid-table">
                        <thead>
                            <tr>
                                <th class="tc">구분</th>
                                <th class="tl">종목코드</th>
                                <th class="tr">체결가</th>
                                <th class="tr">수량</th>
                                <th class="tr">금액</th>
                                <th class="tr">수수료</th>
                                <th class="tr">손익</th>
                                <th class="tr">체결후잔고</th>
                                <th class="tr">체결시각</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="row in trade.list" :key="row.trade_id">
                                <td class="tc"><span :class="['action-badge', actionCls(row.action_type)]">{{ actionLabel(row.action_type) }}</span></td>
                                <td class="tl"><span class="code-chip">{{ row.stock_code }}</span></td>
                                <td class="tr num">{{ fmtWon(row.price) }}</td>
                                <td class="tr num">{{ fmtQty(row.quantity) }}</td>
                                <td class="tr num">{{ fmtWon(row.total_amount) }}</td>
                                <td class="tr num">{{ fmtWon(row.fee) }}</td>
                                <td class="tr num" :class="pnlCls(row.pnl)">{{ fmtSigned(row.pnl) }}</td>
                                <td class="tr num">{{ fmtWon(row.krw_balance) }}</td>
                                <td class="tr num time">{{ formatDateTime(row.exec_time) }}</td>
                            </tr>
                            <tr v-if="trade.list.length === 0"><td colspan="9" class="empty-cell">체결 내역이 없습니다.</td></tr>
                        </tbody>
                    </table>
                </section>

                <section class="mobile-list">
                    <div v-if="trade.loading" class="loader-rows"><div v-for="n in 3" :key="n" class="skeleton-row"></div></div>
                    <ul v-else class="m-ul">
                        <li v-for="row in trade.list" :key="row.trade_id" class="m-li">
                            <div class="li-top">
                                <span :class="['action-badge', actionCls(row.action_type)]">{{ actionLabel(row.action_type) }}</span>
                                <span class="code-chip">{{ row.stock_code }}</span>
                            </div>
                            <div class="li-row"><span class="li-label">체결</span><span>{{ fmtWon(row.price) }} × {{ fmtQty(row.quantity) }} = {{ fmtWon(row.total_amount) }}원</span></div>
                            <div class="li-row" v-if="row.pnl != null"><span class="li-label">손익</span><span class="num" :class="pnlCls(row.pnl)">{{ fmtSigned(row.pnl) }}</span></div>
                            <div class="li-time">{{ formatDateTime(row.exec_time) }}</div>
                        </li>
                        <li v-if="trade.list.length === 0" class="empty-cell">체결 내역이 없습니다.</li>
                    </ul>
                </section>

                <Pagination :state="trade" @go="goTrade" />
            </div>

            <!-- ══ 탭2: 매매 이력 (positions/history) ══ -->
            <div v-show="activeTab === 'history'">
                <section class="filter-bar">
                    <div class="filter-group">
                        <span class="filter-label">상태</span>
                        <div class="chip-group">
                            <button v-for="o in statusOptions" :key="o.value"
                                :class="['filter-chip', { active: histFilter.status === o.value }]"
                                @click="setHistFilter(o.value)">{{ o.label }}</button>
                        </div>
                    </div>
                </section>

                <section class="table-section">
                    <div v-if="hist.loading" class="loader-rows"><div v-for="n in 6" :key="n" class="skeleton-row"></div></div>
                    <table v-else class="grid-table">
                        <thead>
                            <tr>
                                <th class="tl">종목</th>
                                <th class="tc">상태</th>
                                <th class="tr">진입가</th>
                                <th class="tr">수량</th>
                                <th class="tr">청산가</th>
                                <th class="tr">실현손익</th>
                                <th class="tl">청산사유</th>
                                <th class="tr">진입시각</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="row in hist.list" :key="row.position_id">
                                <td class="tl">
                                    <div class="stk">
                                        <span class="code-chip">{{ row.stock_code }}</span>
                                        <span class="stk-name">{{ row.stock_name }}</span>
                                    </div>
                                </td>
                                <td class="tc"><span :class="['status-badge', statusCls(row.status)]">{{ statusLabel(row.status) }}</span></td>
                                <td class="tr num">{{ fmtWon(row.entry_price) }}</td>
                                <td class="tr num">{{ fmtQty(row.qty) }}</td>
                                <td class="tr num">{{ fmtWon(row.exit_price) }}</td>
                                <td class="tr num" :class="pnlCls(row.pnl)">{{ fmtSigned(row.pnl) }}</td>
                                <td class="tl reason">{{ row.exit_reason ?? row.sell_reason ?? '-' }}</td>
                                <td class="tr num time">{{ formatDateTime(row.entry_at) }}</td>
                            </tr>
                            <tr v-if="hist.list.length === 0"><td colspan="8" class="empty-cell">매매 이력이 없습니다.</td></tr>
                        </tbody>
                    </table>
                </section>

                <section class="mobile-list">
                    <div v-if="hist.loading" class="loader-rows"><div v-for="n in 3" :key="n" class="skeleton-row"></div></div>
                    <ul v-else class="m-ul">
                        <li v-for="row in hist.list" :key="row.position_id" class="m-li">
                            <div class="li-top">
                                <span class="code-chip">{{ row.stock_code }}</span>
                                <span :class="['status-badge', statusCls(row.status)]">{{ statusLabel(row.status) }}</span>
                            </div>
                            <div class="li-name">{{ row.stock_name }}</div>
                            <div class="li-row"><span class="li-label">진입/청산</span><span>{{ fmtWon(row.entry_price) }} → {{ fmtWon(row.exit_price) }}</span></div>
                            <div class="li-row" v-if="row.pnl != null"><span class="li-label">실현손익</span><span class="num" :class="pnlCls(row.pnl)">{{ fmtSigned(row.pnl) }}</span></div>
                            <div class="li-row" v-if="row.exit_reason || row.sell_reason"><span class="li-label">사유</span><span>{{ row.exit_reason ?? row.sell_reason }}</span></div>
                            <div class="li-time">{{ formatDateTime(row.entry_at) }}</div>
                        </li>
                        <li v-if="hist.list.length === 0" class="empty-cell">매매 이력이 없습니다.</li>
                    </ul>
                </section>

                <Pagination :state="hist" @go="goHist" />
            </div>

            <!-- ══ 탭3: 운영 로그 (worker-logs) ══ -->
            <div v-show="activeTab === 'worker'">
                <section class="filter-bar">
                    <div class="filter-group">
                        <span class="filter-label">구분</span>
                        <div class="chip-group">
                            <button v-for="o in sourceOptions" :key="o.value"
                                :class="['filter-chip', { active: workerFilter.source === o.value }]"
                                @click="setWorkerFilter('source', o.value)">{{ o.label }}</button>
                        </div>
                    </div>
                    <div class="filter-group">
                        <span class="filter-label">레벨</span>
                        <div class="chip-group">
                            <button v-for="o in levelOptions" :key="o.value"
                                :class="['filter-chip', { active: workerFilter.level === o.value }]"
                                @click="setWorkerFilter('level', o.value)">{{ o.label }}</button>
                        </div>
                    </div>
                </section>

                <section class="table-section">
                    <div v-if="worker.loading" class="loader-rows"><div v-for="n in 6" :key="n" class="skeleton-row"></div></div>
                    <table v-else class="grid-table">
                        <thead>
                            <tr>
                                <th class="tl">ID</th>
                                <th class="tc">구분</th>
                                <th class="tc">레벨</th>
                                <th class="tl">메시지</th>
                                <th class="tr">기록 시각</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="row in worker.list" :key="row.log_id">
                                <td class="tl"><span class="code-chip">{{ row.log_id }}</span></td>
                                <td class="tc"><span :class="['source-badge', srcCls(row.source)]">{{ srcLabel(row.source) }}</span></td>
                                <td class="tc"><span :class="['level-badge', lvlCls(row.level)]">{{ row.level ?? '-' }}</span></td>
                                <td class="tl msg">{{ row.message ?? '-' }}</td>
                                <td class="tr num time">{{ formatDateTime(row.created_at) }}</td>
                            </tr>
                            <tr v-if="worker.list.length === 0"><td colspan="5" class="empty-cell">운영 로그가 없습니다.</td></tr>
                        </tbody>
                    </table>
                </section>

                <section class="mobile-list">
                    <div v-if="worker.loading" class="loader-rows"><div v-for="n in 4" :key="n" class="skeleton-row"></div></div>
                    <ul v-else class="m-ul">
                        <li v-for="row in worker.list" :key="row.log_id" class="m-li">
                            <div class="li-top">
                                <div class="li-badges">
                                    <span :class="['source-badge', srcCls(row.source)]">{{ srcLabel(row.source) }}</span>
                                    <span :class="['level-badge', lvlCls(row.level)]">{{ row.level ?? '-' }}</span>
                                </div>
                                <span class="code-chip">#{{ row.log_id }}</span>
                            </div>
                            <div class="li-msg">{{ row.message ?? '-' }}</div>
                            <div class="li-time">{{ formatDateTime(row.created_at) }}</div>
                        </li>
                        <li v-if="worker.list.length === 0" class="empty-cell">운영 로그가 없습니다.</li>
                    </ul>
                </section>

                <Pagination :state="worker" @go="goWorker" />
            </div>

        </div>
    </div>
</template>

<script setup>
import { h } from 'vue';
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores';

const title = ref('거래 내역');

const userSession = assUserSession();
const userId = computed(() => userSession.user?.loginInfo?.user_id);

const tabs = [
    { key: 'trade', label: '거래 체결' },
    { key: 'history', label: '매매 이력' },
    { key: 'worker', label: '운영 로그' },
];
const activeTab = ref('trade');
const loaded = reactive({ trade: false, history: false, worker: false });

const LIMIT = 20;
// 각 탭의 목록/페이징 상태 (Pagination 컴포넌트가 limit/offset/total 사용)
const makeState = () => reactive({ list: [], loading: true, limit: LIMIT, offset: 0, total: 0 });
const trade = makeState();
const hist = makeState();
const worker = makeState();

/* ── 필터 옵션 ── */
const actionOptions = [{ value: '', label: '전체' }, { value: 'BUY', label: '매수' }, { value: 'SELL', label: '매도' }];
const statusOptions = [{ value: '', label: '전체' }, { value: 'HOLDING', label: '보유중' }, { value: 'SOLD', label: '청산' }];
const sourceOptions = [{ value: '', label: '전체' }, { value: 'buy', label: '매수' }, { value: 'sell', label: '매도' }];
const levelOptions = [{ value: '', label: '전체' }, { value: 'INFO', label: 'INFO' }, { value: 'WARN', label: 'WARN' }];

const tradeFilter = reactive({ action: '', stock_code: '', from: '', to: '' });
const histFilter = reactive({ status: '' });
const workerFilter = reactive({ source: '', level: '' });

/* ── fetch: 거래 체결 ── */
const fetchTrade = async () => {
    trade.loading = true;
    try {
        const params = { limit: trade.limit, offset: trade.offset };
        if (tradeFilter.action) params.action = tradeFilter.action;
        if (tradeFilter.stock_code) params.stock_code = tradeFilter.stock_code;
        if (tradeFilter.from) params.from = tradeFilter.from;
        if (tradeFilter.to) params.to = tradeFilter.to;
        const { data } = await aibeesApi.get(`/api/v1/users/${userId.value}/trade-logs`, { params });
        trade.list = data?.data ?? [];
        trade.total = data?.page?.total ?? 0;
    } finally {
        trade.loading = false;
    }
};

/* ── fetch: 매매 이력 ── */
const fetchHist = async () => {
    hist.loading = true;
    try {
        const params = { limit: hist.limit, offset: hist.offset };
        if (histFilter.status) params.status = histFilter.status;
        const { data } = await aibeesApi.get(`/api/v1/users/${userId.value}/positions/history`, { params });
        hist.list = data?.data ?? [];
        hist.total = data?.page?.total ?? 0;
    } finally {
        hist.loading = false;
    }
};

/* ── fetch: 운영 로그 ── */
const fetchWorker = async () => {
    worker.loading = true;
    try {
        const params = { limit: worker.limit, offset: worker.offset };
        if (workerFilter.source) params.source = workerFilter.source;
        if (workerFilter.level) params.level = workerFilter.level;
        const { data } = await aibeesApi.get(`/api/v1/users/${userId.value}/worker-logs`, { params });
        worker.list = data?.data ?? [];
        worker.total = data?.page?.total ?? 0;
    } finally {
        worker.loading = false;
    }
};

/* ── 탭 전환(지연 로딩) ── */
const loaderMap = { trade: fetchTrade, history: fetchHist, worker: fetchWorker };
const switchTab = (key) => {
    activeTab.value = key;
    if (!loaded[key]) { loaded[key] = true; loaderMap[key](); }
};
const reloadCurrent = () => loaderMap[activeTab.value]();

/* ── 필터 적용 (offset 리셋) ── */
const applyTradeFilter = () => { trade.offset = 0; fetchTrade(); };
const setTradeFilter = (k, v) => { if (tradeFilter[k] === v) return; tradeFilter[k] = v; trade.offset = 0; fetchTrade(); };
const setHistFilter = (v) => { if (histFilter.status === v) return; histFilter.status = v; hist.offset = 0; fetchHist(); };
const setWorkerFilter = (k, v) => { if (workerFilter[k] === v) return; workerFilter[k] = v; worker.offset = 0; fetchWorker(); };

/* ── 페이지 이동 ── */
const goTrade = (offset) => { trade.offset = offset; fetchTrade(); };
const goHist = (offset) => { hist.offset = offset; fetchHist(); };
const goWorker = (offset) => { worker.offset = offset; fetchWorker(); };

onMounted(() => { loaded.trade = true; fetchTrade(); });

/* ── 페이지네이션 컴포넌트 (limit/offset/total envelope) ── */
const Pagination = {
    props: { state: { type: Object, required: true } },
    emits: ['go'],
    setup(props, { emit }) {
        const totalPages = computed(() => Math.ceil((props.state.total || 0) / props.state.limit) || 0);
        const cur = computed(() => Math.floor(props.state.offset / props.state.limit));
        const go = (p) => {
            if (p < 0 || p > totalPages.value - 1) return;
            emit('go', p * props.state.limit);
        };
        return () => {
            if (props.state.loading || totalPages.value <= 1) return null;
            const btn = (label, page, disabled) =>
                h('button', { class: 'page-btn', disabled, onClick: () => go(page) }, label);
            return h('section', { class: 'pagination' }, [
                btn('처음', 0, cur.value === 0),
                btn('이전', cur.value - 1, cur.value === 0),
                h('span', { class: 'page-info' }, `${cur.value + 1} / ${totalPages.value}`),
                btn('다음', cur.value + 1, cur.value >= totalPages.value - 1),
                btn('마지막', totalPages.value - 1, cur.value >= totalPages.value - 1),
            ]);
        };
    },
};

/* ── 포맷/배지 헬퍼 ── */
const toNum = (v) => (v === null || v === undefined || v === '') ? null : Number(v);
const fmtWon = (v) => { const n = toNum(v); return n === null || Number.isNaN(n) ? '-' : n.toLocaleString(undefined, { maximumFractionDigits: 0 }); };
const fmtQty = (v) => { const n = toNum(v); return n === null || Number.isNaN(n) ? '-' : n.toLocaleString(undefined, { maximumFractionDigits: 4 }); };
const fmtSigned = (v) => {
    const n = toNum(v);
    if (n === null || Number.isNaN(n)) return '-';
    const s = n.toLocaleString(undefined, { maximumFractionDigits: 0 });
    return n > 0 ? `+${s}` : s;
};
// 국내 관례: 이익=적색, 손실=청색
const pnlCls = (v) => { const n = toNum(v); if (n === null || n === 0) return ''; return n > 0 ? 'up' : 'down'; };

const actionLabel = (a) => a === 'BUY' ? '매수' : a === 'SELL' ? '매도' : (a ?? '-');
const actionCls = (a) => a === 'BUY' ? 'buy' : a === 'SELL' ? 'sell' : 'default';
const statusLabel = (s) => s === 'HOLDING' ? '보유중' : s === 'SOLD' ? '청산' : (s ?? '-');
const statusCls = (s) => s === 'HOLDING' ? 'holding' : s === 'SOLD' ? 'sold' : 'default';
const srcLabel = (s) => s === 'buy' ? '매수' : s === 'sell' ? '매도' : (s ?? '-');
const srcCls = (s) => s === 'buy' ? 'buy' : s === 'sell' ? 'sell' : 'default';
const lvlCls = (l) => { switch (l) { case 'INFO': return 'info'; case 'WARN': return 'warn'; case 'ERROR': return 'error'; default: return 'default'; } };

const formatDateTime = (v) => v ? String(v).replace('T', ' ').replace(/\.\d+Z?$/, '').slice(0, 19) : '-';
</script>

<style scoped lang="scss">
$white: #ffffff;
$gray-50: #f8f9fa;
$gray-100: #ebebeb;
$gray-200: #d0d0d0;
$gray-400: #909090;
$gray-500: #6b6b6b;
$gray-700: #333333;
$gray-900: #111111;
$blue: #1971c2;
$navy: #1c3d6e;
$red: #c92a2a;
$amber: #e67700;
$green: #2f9e44;

#trade-log {
    min-height: 100vh;
    background: $gray-50;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

.contents { max-width: 1200px; margin: 0 auto; padding: 28px 16px 100px; }

/* Head */
.head-desc {
    display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 18px;
    h2 { font-size: 1.4rem; font-weight: 700; margin: 0; }
    .sub-text { font-size: 0.82rem; color: $gray-500; margin: 4px 0 0; }
    @media (max-width: 600px) { flex-direction: column; align-items: flex-start; gap: 12px; }
}

.btn-refresh {
    display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px;
    background: $navy; color: $white; border: none; border-radius: 0.4rem;
    font-size: 0.84rem; font-weight: 600; cursor: pointer; font-family: inherit; transition: background .15s;
    &:hover { background: darken(#1c3d6e, 6%); }
}

/* Tabs */
.tab-nav { display: flex; gap: 4px; border-bottom: 1px solid $gray-200; margin-bottom: 16px; }
.tab-btn {
    padding: 9px 18px; border: none; background: none; color: $gray-500;
    font-size: 0.86rem; font-weight: 600; cursor: pointer; font-family: inherit;
    border-bottom: 2px solid transparent; margin-bottom: -1px; transition: color .12s, border-color .12s;
    &:hover { color: $gray-700; }
    &.active { color: $navy; border-bottom-color: $navy; }
}

/* Filter bar */
.filter-bar {
    display: flex; flex-wrap: wrap; align-items: center; gap: 18px;
    margin-bottom: 16px; padding: 14px 16px;
    background: $white; border: 1px solid $gray-200; border-radius: 0.6rem;
}
.filter-group { display: flex; align-items: center; gap: 10px; }
.filter-label { font-size: 0.76rem; font-weight: 700; color: $gray-500; letter-spacing: .03em; }
.chip-group { display: flex; gap: 6px; }
.filter-chip {
    padding: 5px 13px; border: 1px solid $gray-200; border-radius: 1rem; background: $white;
    color: $gray-700; font-size: 0.78rem; font-weight: 600; cursor: pointer; font-family: inherit; transition: all .12s;
    &:hover { border-color: $blue; color: $blue; }
    &.active { background: $navy; border-color: $navy; color: $white; }
}
.filter-input {
    padding: 6px 10px; border: 1px solid $gray-200; border-radius: 0.4rem;
    font-size: 0.8rem; color: $gray-900; font-family: inherit; outline: none; transition: border-color .15s;
    &:focus { border-color: $blue; }
    &.date { padding: 5px 8px; }
}
.tilde { color: $gray-400; }
.btn-apply {
    padding: 7px 18px; border: none; border-radius: 0.4rem; background: $navy; color: $white;
    font-size: 0.82rem; font-weight: 700; cursor: pointer; font-family: inherit; transition: background .15s;
    &:hover { background: darken(#1c3d6e, 6%); }
}

/* Table */
.table-section {
    background: $white; border: 1px solid $gray-200; border-radius: 0.6rem;
    overflow: hidden; overflow-x: auto;
    @media (max-width: 860px) { display: none; }
}
.grid-table {
    width: 100%; border-collapse: collapse; font-size: 0.83rem;
    thead tr { background: $gray-50; border-bottom: 1px solid $gray-200; }
    th { padding: 10px 12px; font-size: 0.72rem; font-weight: 700; color: $gray-500; letter-spacing: .03em; white-space: nowrap; }
    td { padding: 10px 12px; border-bottom: 1px solid $gray-100; color: $gray-700; white-space: nowrap; }
    tbody tr:last-child td { border-bottom: none; }
    tbody tr:hover td { background: $gray-50; }
    .tl { text-align: left; } .tr { text-align: right; } .tc { text-align: center; }
    .num { font-variant-numeric: tabular-nums; }
    .time { color: $gray-500; font-size: 0.78rem; }
    .up { color: $red; font-weight: 600; } .down { color: $blue; font-weight: 600; }
    .msg { white-space: normal; word-break: break-all; min-width: 260px; }
    .reason { white-space: normal; word-break: break-all; min-width: 160px; color: $gray-500; }
}
.stk { display: flex; align-items: center; gap: 8px; }
.stk-name { color: $gray-900; }

.code-chip {
    font-size: 0.72rem; font-weight: 600; background: $gray-100; color: $gray-700;
    padding: 2px 7px; border-radius: 0.3rem; border: 1px solid $gray-200;
    font-family: 'SFMono-Regular', Consolas, monospace;
}

.action-badge, .source-badge, .status-badge {
    font-size: 0.7rem; font-weight: 700; padding: 2px 9px; border-radius: 0.3rem; white-space: nowrap;
    &.buy { background: #ffe3e3; color: $red; border: 1px solid #ffa8a8; }
    &.sell { background: #d0ebff; color: $blue; border: 1px solid #74c0fc; }
    &.holding { background: #e7f5ff; color: $blue; border: 1px solid #a5d8ff; }
    &.sold { background: $gray-100; color: $gray-700; border: 1px solid $gray-200; }
    &.default { background: $gray-100; color: $gray-500; border: 1px solid $gray-200; }
}
.level-badge {
    font-size: 0.7rem; font-weight: 700; padding: 2px 8px; border-radius: 0.3rem; white-space: nowrap;
    &.info { background: #d3f9d8; color: $green; border: 1px solid #8ce99a; }
    &.warn { background: #fff0b3; color: $amber; border: 1px solid #ffd43b; }
    &.error { background: #ffe3e3; color: $red; border: 1px solid #ffa8a8; }
    &.default { background: $gray-100; color: $gray-500; border: 1px solid $gray-200; }
}

/* skeleton / empty */
.loader-rows { padding: 8px; }
.skeleton-row { height: 42px; background: $gray-100; border-radius: 0.4rem; margin-bottom: 6px; animation: pulse 1.6s infinite ease-in-out; }
.empty-cell { text-align: center; padding: 60px 0; color: $gray-400; font-size: 0.88rem; }

/* Mobile */
.mobile-list { display: none; @media (max-width: 860px) { display: block; } }
.m-ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.m-li { background: $white; border: 1px solid $gray-200; border-radius: 0.6rem; padding: 14px; }
.li-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.li-badges { display: flex; gap: 6px; }
.li-name { font-size: 0.95rem; font-weight: 700; color: $gray-900; margin-bottom: 8px; }
.li-msg { font-size: 0.86rem; color: $gray-900; line-height: 1.5; word-break: break-all; margin-bottom: 8px; }
.li-row {
    display: flex; gap: 8px; font-size: 0.8rem; margin-bottom: 4px; color: $gray-700;
    .li-label { flex-shrink: 0; width: 68px; color: $gray-500; font-weight: 600; }
}
.li-time { font-size: 0.76rem; color: $gray-500; font-variant-numeric: tabular-nums; }
.num.up { color: $red; } .num.down { color: $blue; }

/* Pagination (렌더 함수 컴포넌트가 생성) */
.pagination { display: flex; justify-content: center; align-items: center; gap: 8px; margin-top: 18px; }
:deep(.page-btn) {
    padding: 6px 14px; border: 1px solid $gray-200; border-radius: 0.4rem; background: $white; color: $gray-700;
    font-size: 0.8rem; font-weight: 600; cursor: pointer; font-family: inherit; transition: border-color .12s, color .12s;
    &:hover:not(:disabled) { border-color: $blue; color: $blue; }
    &:disabled { opacity: .45; cursor: not-allowed; }
}
:deep(.page-info) { font-size: 0.82rem; font-weight: 600; color: $gray-700; padding: 0 6px; }

@keyframes pulse { 0%, 100% { opacity: .5; } 50% { opacity: .9; } }
</style>
