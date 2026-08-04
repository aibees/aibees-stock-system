<template>
    <div id="my-wallet">
        <Headers :prop_title="title" />

        <div class="contents">

            <!-- ── 상단 타이틀 ── -->
            <section class="head-desc">
                <div class="head-left">
                    <h2>계좌 현황</h2>
                    <p class="sub-text">
                        증권사 계좌와 동기화된 자산 스냅샷입니다
                        <span v-if="account?.updated_at" class="basis-time">· 기준시각 {{ formatDateTime(account.updated_at) }}</span>
                    </p>
                </div>
                <div class="head-right">
                    <button class="btn-refresh" @click="reloadAll">
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

            <!-- ── 계좌 요약 카드 ── -->
            <section class="summary-cards">
                <div class="s-card total" :class="{ skeleton: loadingAccount }">
                    <template v-if="!loadingAccount">
                        <div class="s-label">총자산</div>
                        <div class="s-amount">{{ fmtWon(account?.total_asset) }}<span class="won">원</span></div>
                    </template>
                </div>
                <div class="s-card" :class="{ skeleton: loadingAccount }">
                    <template v-if="!loadingAccount">
                        <div class="s-label">예수금</div>
                        <div class="s-amount sub">{{ fmtWon(account?.user_balance) }}<span class="won">원</span></div>
                    </template>
                </div>
                <div class="s-card" :class="{ skeleton: loadingAccount }">
                    <template v-if="!loadingAccount">
                        <div class="s-label">주식평가액</div>
                        <div class="s-amount sub">{{ fmtWon(account?.stock_amount) }}<span class="won">원</span></div>
                    </template>
                </div>
            </section>

            <!-- ── 탭 ── -->
            <nav class="tab-nav">
                <button v-for="t in tabs" :key="t.key" :class="['tab-btn', { active: activeTab === t.key }]"
                    @click="switchTab(t.key)">
                    {{ t.label }}
                </button>
            </nav>

            <!-- ══ 탭1: 보유종목 (portfolio) ══ -->
            <div v-show="activeTab === 'holdings'">
                <section class="table-section">
                    <div v-if="loadingPortfolio" class="loader-rows">
                        <div v-for="n in 5" :key="n" class="skeleton-row"></div>
                    </div>
                    <table v-else class="grid-table">
                        <thead>
                            <tr>
                                <th class="tl">종목코드</th>
                                <th class="tl">종목명</th>
                                <th class="tr">수량</th>
                                <th class="tr">매입가</th>
                                <th class="tr">현재가</th>
                                <th class="tr">평가금액</th>
                                <th class="tr">평가손익</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="row in holdings" :key="row.stock_code">
                                <td class="tl"><span class="code-chip">{{ row.stock_code }}</span></td>
                                <td class="tl name">{{ row.stock_name }}</td>
                                <td class="tr num">{{ fmtQty(row.qty) }}</td>
                                <td class="tr num">{{ fmtWon(row.avg_price) }}</td>
                                <td class="tr num">{{ fmtWon(row.cur_price) }}</td>
                                <td class="tr num">{{ fmtWon(row.eval_amount) }}</td>
                                <td class="tr num" :class="pnlClass(row.profit)">{{ fmtSigned(row.profit) }}</td>
                            </tr>
                            <tr v-if="holdings.length === 0">
                                <td colspan="7" class="empty-cell">보유 종목이 없습니다.</td>
                            </tr>
                        </tbody>
                        <tfoot v-if="summary && holdings.length > 0">
                            <tr class="total-row">
                                <td class="tl" colspan="5">합계</td>
                                <td class="tr num">{{ fmtWon(summary.stock_amount) }}</td>
                                <td class="tr num sub-note">예수금 {{ fmtWon(summary.cash) }}</td>
                            </tr>
                        </tfoot>
                    </table>
                </section>

                <!-- 모바일 -->
                <section class="mobile-list">
                    <div v-if="loadingPortfolio" class="loader-rows">
                        <div v-for="n in 3" :key="n" class="skeleton-row"></div>
                    </div>
                    <ul v-else class="m-ul">
                        <li v-for="row in holdings" :key="row.stock_code" class="m-li">
                            <div class="li-top">
                                <span class="code-chip">{{ row.stock_code }}</span>
                                <span class="num" :class="pnlClass(row.profit)">{{ fmtSigned(row.profit) }}</span>
                            </div>
                            <div class="li-name">{{ row.stock_name }}</div>
                            <div class="li-row"><span class="li-label">수량</span><span>{{ fmtQty(row.qty) }}</span></div>
                            <div class="li-row"><span class="li-label">매입/현재</span><span>{{ fmtWon(row.avg_price) }} / {{ fmtWon(row.cur_price) }}</span></div>
                            <div class="li-row"><span class="li-label">평가금액</span><span>{{ fmtWon(row.eval_amount) }} 원</span></div>
                        </li>
                        <li v-if="holdings.length === 0" class="empty-cell">보유 종목이 없습니다.</li>
                    </ul>
                </section>
            </div>

            <!-- ══ 탭2: worker 포지션 (positions HOLDING) ══ -->
            <div v-show="activeTab === 'positions'">
                <section class="table-section">
                    <div v-if="loadingPositions" class="loader-rows">
                        <div v-for="n in 5" :key="n" class="skeleton-row"></div>
                    </div>
                    <table v-else class="grid-table">
                        <thead>
                            <tr>
                                <th class="tl">종목</th>
                                <th class="tr">진입가</th>
                                <th class="tr">수량</th>
                                <th class="tr">손절</th>
                                <th class="tr">익절</th>
                                <th class="tr">트레일</th>
                                <th class="tr">수익률</th>
                                <th class="tc">판정</th>
                                <th class="tr">보유일</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="row in positions" :key="row.position_id">
                                <td class="tl">
                                    <div class="stk">
                                        <span class="code-chip">{{ row.stock_code }}</span>
                                        <span class="stk-name">{{ row.stock_name }}</span>
                                    </div>
                                </td>
                                <td class="tr num">{{ fmtWon(row.entry_price) }}</td>
                                <td class="tr num">{{ fmtQty(row.qty) }}</td>
                                <td class="tr num stop">{{ fmtWon(row.stop_price) }}</td>
                                <td class="tr num target">{{ fmtWon(row.target_price) }}</td>
                                <td class="tr num">{{ fmtWon(row.trail_line) }}</td>
                                <td class="tr num" :class="pctClass(row.profit_pct)">{{ row.profit_pct ?? '-' }}</td>
                                <td class="tc"><span :class="['action-badge', actionClass(row.action_type)]">{{ row.action_type ?? '-' }}</span></td>
                                <td class="tr num">{{ row.bars_held ?? '-' }}</td>
                            </tr>
                            <tr v-if="positions.length === 0">
                                <td colspan="9" class="empty-cell">worker 가 보유 중인 포지션이 없습니다.</td>
                            </tr>
                        </tbody>
                    </table>
                </section>

                <!-- 모바일 -->
                <section class="mobile-list">
                    <div v-if="loadingPositions" class="loader-rows">
                        <div v-for="n in 3" :key="n" class="skeleton-row"></div>
                    </div>
                    <ul v-else class="m-ul">
                        <li v-for="row in positions" :key="row.position_id" class="m-li">
                            <div class="li-top">
                                <span class="code-chip">{{ row.stock_code }}</span>
                                <span :class="['action-badge', actionClass(row.action_type)]">{{ row.action_type ?? '-' }}</span>
                            </div>
                            <div class="li-name">{{ row.stock_name }} <span class="pct" :class="pctClass(row.profit_pct)">{{ row.profit_pct ?? '' }}</span></div>
                            <div class="li-row"><span class="li-label">진입가</span><span>{{ fmtWon(row.entry_price) }} · {{ fmtQty(row.qty) }}주</span></div>
                            <div class="li-row"><span class="li-label">손/익/트레일</span><span>{{ fmtWon(row.stop_price) }} / {{ fmtWon(row.target_price) }} / {{ fmtWon(row.trail_line) }}</span></div>
                            <div class="li-row" v-if="row.sell_reason"><span class="li-label">근거</span><span>{{ row.sell_reason }}</span></div>
                        </li>
                        <li v-if="positions.length === 0" class="empty-cell">보유 중인 포지션이 없습니다.</li>
                    </ul>
                </section>
            </div>

        </div>
    </div>
</template>

<script setup>
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores';

const title = ref('계좌 현황');

const userSession = assUserSession();
const userId = computed(() => userSession.user?.loginInfo?.user_id);

const tabs = [
    { key: 'holdings', label: '보유종목' },
    { key: 'positions', label: 'worker 포지션' },
];
const activeTab = ref('holdings');
const positionsLoaded = ref(false);

/* ── 상태 ── */
const account = ref(null);
const holdings = ref([]);
const summary = ref(null);
const positions = ref([]);

const loadingAccount = ref(true);
const loadingPortfolio = ref(true);
const loadingPositions = ref(true);

/* ── fetch ── */
const fetchAccount = async () => {
    loadingAccount.value = true;
    try {
        const { data } = await aibeesApi.get(`/api/v1/users/${userId.value}/account`);
        account.value = data ?? null;
    } finally {
        loadingAccount.value = false;
    }
};

const fetchPortfolio = async () => {
    loadingPortfolio.value = true;
    try {
        const { data } = await aibeesApi.get(`/api/v1/users/${userId.value}/portfolio`);
        holdings.value = data?.holdings ?? [];
        summary.value = data?.summary ?? null;
    } finally {
        loadingPortfolio.value = false;
    }
};

const fetchPositions = async () => {
    loadingPositions.value = true;
    try {
        const { data } = await aibeesApi.get(`/api/v1/users/${userId.value}/positions`, {
            params: { status: 'HOLDING', limit: 100, offset: 0 },
        });
        positions.value = data?.data ?? [];
        positionsLoaded.value = true;
    } finally {
        loadingPositions.value = false;
    }
};

const switchTab = (key) => {
    activeTab.value = key;
    if (key === 'positions' && !positionsLoaded.value) fetchPositions();
};

const reloadAll = () => {
    fetchAccount();
    fetchPortfolio();
    if (activeTab.value === 'positions' || positionsLoaded.value) fetchPositions();
};

onMounted(() => {
    fetchAccount();
    fetchPortfolio();
});

/* ── 헬퍼 ── */
const toNum = (v) => (v === null || v === undefined || v === '') ? null : Number(v);

const fmtWon = (v) => {
    const n = toNum(v);
    return n === null || Number.isNaN(n) ? '-' : n.toLocaleString(undefined, { maximumFractionDigits: 0 });
};
const fmtQty = (v) => {
    const n = toNum(v);
    return n === null || Number.isNaN(n) ? '-' : n.toLocaleString(undefined, { maximumFractionDigits: 4 });
};
const fmtSigned = (v) => {
    const n = toNum(v);
    if (n === null || Number.isNaN(n)) return '-';
    const s = n.toLocaleString(undefined, { maximumFractionDigits: 0 });
    return n > 0 ? `+${s}` : s;
};
// 국내 관례: 이익=적색, 손실=청색
const pnlClass = (v) => {
    const n = toNum(v);
    if (n === null || n === 0) return '';
    return n > 0 ? 'up' : 'down';
};
const pctClass = (v) => {
    if (v === null || v === undefined) return '';
    const n = parseFloat(String(v).replace('%', ''));
    if (Number.isNaN(n) || n === 0) return '';
    return n > 0 ? 'up' : 'down';
};
const actionClass = (a) => {
    if (!a) return 'default';
    if (a === 'HOLD') return 'hold';
    if (a.startsWith('SELL')) return 'sell';
    return 'default';
};

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

#my-wallet {
    min-height: 100vh;
    background: $gray-50;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

.contents {
    max-width: 1200px;
    margin: 0 auto;
    padding: 28px 16px 100px;
}

/* Head */
.head-desc {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 20px;

    h2 { font-size: 1.4rem; font-weight: 700; margin: 0; }
    .sub-text { font-size: 0.82rem; color: $gray-500; margin: 4px 0 0; }
    .basis-time { color: $gray-400; }

    @media (max-width: 600px) { flex-direction: column; align-items: flex-start; gap: 12px; }
}

.btn-refresh {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 16px; background: $navy; color: $white; border: none;
    border-radius: 0.4rem; font-size: 0.84rem; font-weight: 600; cursor: pointer;
    font-family: inherit; transition: background .15s;
    &:hover { background: darken(#1c3d6e, 6%); }
}

/* Summary cards */
.summary-cards {
    display: grid;
    grid-template-columns: 1.3fr 1fr 1fr;
    gap: 12px;
    margin-bottom: 22px;

    @media (max-width: 600px) { grid-template-columns: 1fr; }
}

.s-card {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.7rem;
    padding: 18px 20px;
    min-height: 92px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, .04);

    &.total { background: $navy; border-color: $navy; }
    &.total .s-label { color: rgba(255,255,255,.7); }
    &.total .s-amount { color: $white; }
    &.total .won { color: rgba(255,255,255,.7); }

    &.skeleton { background: $gray-100; border: none; animation: pulse 1.6s infinite ease-in-out; }
}

.s-label {
    font-size: 0.74rem; font-weight: 700; color: $gray-500;
    letter-spacing: .04em; text-transform: uppercase; margin-bottom: 10px;
}

.s-amount {
    font-size: 1.8rem; font-weight: 800; color: $navy;
    font-variant-numeric: tabular-nums; line-height: 1.1;
    &.sub { font-size: 1.35rem; color: $gray-900; }
    .won { font-size: 0.9rem; font-weight: 600; color: $gray-500; margin-left: 4px; }
}

/* Tabs */
.tab-nav {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid $gray-200;
    margin-bottom: 16px;
}

.tab-btn {
    padding: 9px 18px;
    border: none;
    background: none;
    color: $gray-500;
    font-size: 0.86rem;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: color .12s, border-color .12s;

    &:hover { color: $gray-700; }
    &.active { color: $navy; border-bottom-color: $navy; }
}

/* Table (Desktop) */
.table-section {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.6rem;
    overflow: hidden;
    overflow-x: auto;
    @media (max-width: 860px) { display: none; }
}

.grid-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.83rem;

    thead tr { background: $gray-50; border-bottom: 1px solid $gray-200; }

    th {
        padding: 10px 12px; font-size: 0.72rem; font-weight: 700; color: $gray-500;
        letter-spacing: .03em; white-space: nowrap;
    }

    td { padding: 10px 12px; border-bottom: 1px solid $gray-100; color: $gray-700; white-space: nowrap; }
    tbody tr:last-child td { border-bottom: none; }
    tbody tr:hover td { background: $gray-50; }

    .tl { text-align: left; }
    .tr { text-align: right; }
    .tc { text-align: center; }
    .num { font-variant-numeric: tabular-nums; }
    .name { color: $gray-900; font-weight: 500; }

    .up { color: $red; font-weight: 600; }
    .down { color: $blue; font-weight: 600; }
    .stop { color: $red; }
    .target { color: $green; }

    tfoot .total-row td {
        background: $gray-50;
        font-weight: 700;
        color: $gray-900;
        border-top: 2px solid $gray-200;
    }
    .sub-note { font-weight: 600; color: $gray-500; font-size: 0.78rem; }
}

.stk { display: flex; align-items: center; gap: 8px; }
.stk-name { color: $gray-900; }

.code-chip {
    font-size: 0.72rem; font-weight: 600; background: $gray-100; color: $gray-700;
    padding: 2px 7px; border-radius: 0.3rem; border: 1px solid $gray-200;
    font-family: 'SFMono-Regular', Consolas, monospace;
}

.action-badge {
    font-size: 0.7rem; font-weight: 700; padding: 2px 8px; border-radius: 0.3rem; white-space: nowrap;
    &.hold { background: #e7f5ff; color: $blue; border: 1px solid #a5d8ff; }
    &.sell { background: #ffe3e3; color: $red; border: 1px solid #ffa8a8; }
    &.default { background: $gray-100; color: $gray-500; border: 1px solid $gray-200; }
}

/* skeleton */
.loader-rows { padding: 8px; }
.skeleton-row {
    height: 42px; background: $gray-100; border-radius: 0.4rem;
    margin-bottom: 6px; animation: pulse 1.6s infinite ease-in-out;
}
.empty-cell { text-align: center; padding: 60px 0; color: $gray-400; font-size: 0.88rem; }

/* Mobile list */
.mobile-list { display: none; @media (max-width: 860px) { display: block; } }
.m-ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.m-li { background: $white; border: 1px solid $gray-200; border-radius: 0.6rem; padding: 14px; }
.li-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.li-name { font-size: 0.95rem; font-weight: 700; color: $gray-900; margin-bottom: 8px; }
.li-name .pct { font-size: 0.82rem; margin-left: 6px; }
.li-row {
    display: flex; gap: 8px; font-size: 0.8rem; margin-bottom: 4px; color: $gray-700;
    .li-label { flex-shrink: 0; width: 76px; color: $gray-500; font-weight: 600; }
}
.up { color: $red; }
.down { color: $blue; }

@keyframes pulse { 0%, 100% { opacity: .5; } 50% { opacity: .9; } }
</style>
