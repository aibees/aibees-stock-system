<template>
    <div id="my-wallet">
        <Headers :prop_title="title" />

        <div class="contents">

            <!-- ── 상단 타이틀 ── -->
            <section class="head-desc">
                <div class="head-left">
                    <h2 style="text-align: left;">계좌 현황</h2>
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

            <!-- ── 계좌 요약 ──
                 증권사 앱(총 자산 화면) 구조를 따른다: 총자산을 한 번만 크게 보여주고
                 평가손익·수익률을 바로 아래 붙인 뒤, 세부 금액은 라벨-값 목록으로
                 내린다. 이전의 4-카드 그리드는 네 값이 같은 비중으로 보여서
                 "내 자산이 얼마인가"가 한눈에 안 들어왔다. -->
            <section class="account-panel" :class="{ skeleton: loadingAccount }">
                <template v-if="!loadingAccount">
                    <div class="ap-total">
                        <div class="ap-total-label">총자산</div>
                        <div class="ap-total-amount">
                            {{ fmtWon(account?.total_asset) }}<span class="won">원</span>
                        </div>
                        <!-- 평가손익/수익률. 분모는 매입금액이다(portfolioTotals.costBasis 주석 참고).
                             보유종목이 없으면 계산할 게 없으므로 숨긴다. -->
                        <div v-if="portfolioTotals.profitPct !== null" class="ap-pnl"
                             :class="pnlClass(portfolioTotals.profitSum)">
                            <span class="ap-pnl-arrow">{{ portfolioTotals.profitSum >= 0 ? '▲' : '▼' }}</span>
                            <span>{{ fmtWon(Math.abs(portfolioTotals.profitSum)) }}원</span>
                            <span class="ap-pnl-sep">|</span>
                            <span>{{ fmtPct(portfolioTotals.profitPct) }}</span>
                        </div>
                    </div>

                    <dl class="ap-rows">
                        <div class="ap-row">
                            <dt>예수금</dt>
                            <dd>{{ fmtWon(account?.deposit) }}원</dd>
                        </div>
                        <div class="ap-row">
                            <dt>매입금액</dt>
                            <dd>{{ fmtWon(portfolioTotals.costBasis) }}원</dd>
                        </div>
                        <div class="ap-row">
                            <dt>평가금액</dt>
                            <dd>{{ fmtWon(account?.stock_amount) }}원</dd>
                        </div>
                        <!-- 주문가능금액(=미수없는매수금액). 예수금과 다른 값이다 —
                             증거금징수율이 반영되고, 미체결 주문에 묶인 금액이 빠져 있다. -->
                        <div class="ap-row">
                            <dt>
                                주문가능금액
                                <!-- title 속성은 데스크톱 hover 에서만 뜨고 터치에서는
                                     아무 일도 일어나지 않는다 → 클릭 토글로 바꿨다. -->
                                <button type="button" class="ap-help" :aria-expanded="showBuyableHelp"
                                        aria-label="주문가능금액 설명"
                                        @click="showBuyableHelp = !showBuyableHelp">?</button>
                            </dt>
                            <dd>{{ fmtWon(account?.user_balance) }}원</dd>
                        </div>
                        <div v-if="showBuyableHelp" class="ap-help-box">{{ buyableHelp }}</div>
                    </dl>
                </template>
            </section>

            <!-- 예수금 ≠ 주문가능금액 인 이유를 한 줄로. 차이가 없으면 띄우지 않는다.
                 방향은 계좌마다 다르다 — 미체결·증거금으로 줄기도 하고,
                 재사용가능금액·대용증권으로 예수금보다 늘기도 한다. -->
            <p v-if="!loadingAccount && cashGap !== 0" class="cash-gap-note">
                <template v-if="cashGap > 0">
                    주문가능금액이 예수금보다 {{ fmtWon(cashGap) }}원 적습니다 — 종목별 증거금징수율과 미체결 주문에 묶인 금액입니다.
                </template>
                <template v-else>
                    주문가능금액이 예수금보다 {{ fmtWon(-cashGap) }}원 많습니다 — 재사용가능금액·대용증권이 반영된 금액입니다.
                </template>
            </p>

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
                                <th class="tr">수익률</th>
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
                                <td class="tr num" :class="pnlClass(rowProfitPct(row))">{{ fmtPct(rowProfitPct(row)) }}</td>
                            </tr>
                            <tr v-if="holdings.length === 0">
                                <td colspan="8" class="empty-cell">보유 종목이 없습니다.</td>
                            </tr>
                        </tbody>
                        <tfoot v-if="summary && holdings.length > 0">
                            <tr class="total-row">
                                <td class="tl" colspan="5">종목 소계</td>
                                <td class="tr num">{{ fmtWon(portfolioTotals.evalAmount) }}</td>
                                <td class="tr num" :class="pnlClass(portfolioTotals.profitSum)">{{ fmtSigned(portfolioTotals.profitSum) }}</td>
                                <td class="tr num" :class="pnlClass(portfolioTotals.profitPct)">{{ fmtPct(portfolioTotals.profitPct) }}</td>
                            </tr>
                            <tr class="total-row sub">
                                <!-- summary.cash = v_user_portfolio TOTAL 행의 예수금(user_wallet.deposit) -->
                                <td class="tl" colspan="5">합계(예수금 포함)</td>
                                <td class="tr num" colspan="3">
                                    {{ fmtWon(summary.stock_amount) }}원
                                    <span class="sub-note">· 예수금 {{ fmtWon(summary.cash) }}원</span>
                                </td>
                            </tr>
                        </tfoot>
                    </table>
                </section>

                <!-- 모바일 -->
                <section class="mobile-list">
                    <div v-if="loadingPortfolio" class="loader-rows">
                        <div v-for="n in 3" :key="n" class="skeleton-row"></div>
                    </div>
                    <template v-else>
                        <div v-if="holdings.length > 0" class="m-subtotal">
                            <span class="m-subtotal-label">종목 소계</span>
                            <span class="m-subtotal-amt">{{ fmtWon(portfolioTotals.evalAmount) }}원</span>
                            <span class="num" :class="pnlClass(portfolioTotals.profitSum)">
                                {{ fmtSigned(portfolioTotals.profitSum) }} ({{ fmtPct(portfolioTotals.profitPct) }})
                            </span>
                        </div>
                        <ul class="m-ul">
                            <li v-for="row in holdings" :key="row.stock_code" class="m-li">
                                <div class="li-top">
                                    <span class="code-chip">{{ row.stock_code }}</span>
                                    <span class="num" :class="pnlClass(row.profit)">
                                        {{ fmtSigned(row.profit) }} ({{ fmtPct(rowProfitPct(row)) }})
                                    </span>
                                </div>
                                <div class="li-name">{{ row.stock_name }}</div>
                                <div class="li-row"><span class="li-label">수량</span><span>{{ fmtQty(row.qty) }}</span></div>
                                <div class="li-row"><span class="li-label">매입/현재</span><span>{{ fmtWon(row.avg_price) }} / {{ fmtWon(row.cur_price) }}</span></div>
                                <div class="li-row"><span class="li-label">평가금액</span><span>{{ fmtWon(row.eval_amount) }} 원</span></div>
                            </li>
                            <li v-if="holdings.length === 0" class="empty-cell">보유 종목이 없습니다.</li>
                        </ul>
                    </template>
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

/* ── 종목별 수익률 / 소계 ── */
// 매입가 대비 현재가 수익률(%). row.profit(평가손익 금액)이 있으면 수량*매입가 대비로,
// 없으면 avg_price/cur_price 로 직접 계산 — 백엔드 응답에 따라 어느 쪽이든 동작하게.
const rowProfitPct = (row) => {
    const avg = toNum(row.avg_price);
    if (avg === null || avg === 0) return null;
    const profit = toNum(row.profit);
    const qty = toNum(row.qty);
    if (profit !== null && qty) return (profit / (avg * qty)) * 100;
    const cur = toNum(row.cur_price);
    if (cur === null) return null;
    return ((cur - avg) / avg) * 100;
};

// 보유종목 전체 소계: 평가금액 합, 평가손익 합, 원가 대비 가중평균 수익률(%).
const portfolioTotals = computed(() => {
    let evalAmount = 0;
    let profitSum = 0;
    let costBasis = 0;
    for (const row of holdings.value) {
        evalAmount += toNum(row.eval_amount) ?? 0;
        profitSum += toNum(row.profit) ?? 0;
        const avg = toNum(row.avg_price);
        const qty = toNum(row.qty);
        if (avg !== null && qty !== null) costBasis += avg * qty;
    }
    return {
        evalAmount,
        profitSum,
        // 매입금액. 계좌 요약(API)에는 없는 값이라 보유종목에서 합산해 만든다.
        // 수익률의 분모이기도 하다 — 총자산으로 나누면 예수금까지 분모에 들어가
        // 실제 투자 성과가 희석된다(증권사 앱도 매입금액 기준으로 표시한다).
        costBasis,
        profitPct: costBasis > 0 ? (profitSum / costBasis) * 100 : null,
    };
});

/* ── 예수금 vs 주문가능금액 ──
   같은 계좌의 서로 다른 값이다.
     deposit      = ord_psbl_cash  주문가능현금
     user_balance = nrcvb_buy_amt  미수없는매수금액 (실제 주문 판단 기준)
   차이는 종목별 증거금징수율과 미체결 주문에 묶인 금액에서 온다. */
// '?' 는 클릭 토글이다. 네이티브 title 속성은 터치 기기에서 뜨지 않아 모바일에서
// 아무 반응이 없었다(사용테스트 피드백).
const showBuyableHelp = ref(false);

const buyableHelp =
    '증거금징수율이 반영되고 미체결 주문에 묶인 금액이 빠진, 지금 실제로 주문 가능한 금액입니다. '
    + '예수금과 다를 수 있습니다.';

const cashGap = computed(() => {
    const d = toNum(account.value?.deposit);
    const b = toNum(account.value?.user_balance);
    if (d === null || b === null || Number.isNaN(d) || Number.isNaN(b)) return 0;
    return d - b;
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
const fmtPct = (v) => {
    const n = toNum(v);
    if (n === null || Number.isNaN(n)) return '-';
    const s = n.toFixed(2);
    return n > 0 ? `+${s}%` : `${s}%`;
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
// 무채색 팔레트(/trade 대시보드와 통일). 변수명은 유지, 값만 회색조로 교체.
$white: #ffffff;
$gray-50: #fafafa;
$gray-100: #efefef;
$gray-200: #dcdcdc;
$gray-300: #c4c4c4;
$gray-400: #9a9a9a;
$gray-500: #737373;
$gray-700: #3d3d3d;
$gray-900: #141414;
$blue: #141414;
$navy: #141414;
$red: #141414;
$amber: #141414;
$green: #141414;

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
    font-size: 0.84rem; font-weight: 600; cursor: pointer;
    font-family: inherit; transition: background .15s;
    &:hover { background: #000000; }
}

/* Summary cards */
/* ── 계좌 요약 패널 ──
 * 증권사 앱 구조: 총자산 1개를 크게 + 손익/수익률, 세부는 라벨-값 목록.
 * 이전 4-카드 그리드(.summary-cards)는 네 값이 같은 비중이라 총자산이 묻혔다. */
.account-panel {
    background: $white;
    border: 1px solid $gray-200;
    margin-bottom: 12px;

    &.skeleton { min-height: 220px; }

    .ap-total {
        padding: 20px 18px 16px;
        border-bottom: 1px solid $gray-100;
        text-align: left;

        .ap-total-label {
            font-size: 0.8rem;
            font-weight: 600;
            color: $gray-500;
            margin-bottom: 6px;
        }

        .ap-total-amount {
            font-size: 1.9rem;
            font-weight: 700;
            color: $gray-900;
            letter-spacing: -0.02em;
            line-height: 1.15;

            .won { font-size: 1.1rem; font-weight: 600; margin-left: 2px; }
        }

        .ap-pnl {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-top: 8px;
            font-size: 0.92rem;
            font-weight: 600;
            color: $gray-500;

            .ap-pnl-arrow { font-size: 0.78rem; }
            .ap-pnl-sep { color: $gray-300; font-weight: 400; }

            /* 상승/하락 색은 기존 .up/.down 과 같은 출처를 쓴다(pnlClass). */
            &.up { color: $red; }
            &.down { color: $blue; }
        }
    }

    .ap-rows {
        margin: 0;
        padding: 6px 18px 14px;

        .ap-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding: 9px 0;

            dt {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                font-size: 0.86rem;
                color: $gray-500;
            }

            dd {
                margin: 0;
                font-size: 0.92rem;
                font-weight: 600;
                color: $gray-900;
                font-variant-numeric: tabular-nums;
            }
        }

        /* 클릭 토글 도움말. title 속성은 터치에서 안 떠서 버튼으로 바꿨다. */
        .ap-help {
            width: 16px;
            height: 16px;
            padding: 0;
            border: 1px solid $gray-300;
            border-radius: 50%;
            background: $white;
            color: $gray-500;
            font-size: 0.68rem;
            font-weight: 700;
            line-height: 1;
            cursor: pointer;

            &[aria-expanded="true"] {
                background: $gray-900;
                border-color: $gray-900;
                color: $white;
            }
        }

        .ap-help-box {
            margin: 2px 0 6px;
            padding: 10px 12px;
            background: $gray-50;
            border: 1px solid $gray-200;
            font-size: 0.8rem;
            line-height: 1.55;
            color: $gray-700;
            text-align: left;
        }
    }
}

.cash-gap-note {
    font-size: 0.78rem;
    color: $gray-500;
    line-height: 1.5;
    margin: 0 0 22px;
}

/* 옛 4-카드 요약(.s-card/.s-label/.s-amount/.s-help)은 .account-panel 로 교체하며 제거했다. */

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
    tfoot .total-row.sub td {
        border-top: none;
        font-weight: 500;
        font-size: 0.78rem;
        color: $gray-500;
    }
    .sub-note { font-weight: 600; color: $gray-500; font-size: 0.78rem; margin-left: 4px; }
}

.stk { display: flex; align-items: center; gap: 8px; }
.stk-name { color: $gray-900; }

.code-chip {
    font-size: 0.72rem; font-weight: 600; background: $gray-100; color: $gray-700;
    padding: 2px 7px; border: 1px solid $gray-200;
    font-family: 'SFMono-Regular', Consolas, monospace;
}

.action-badge {
    font-size: 0.7rem; font-weight: 700; padding: 2px 8px; white-space: nowrap;
    &.hold { background: $gray-100; color: $gray-900; border: 1px solid $gray-300; }
    &.sell { background: $gray-900; color: $white; border: 1px solid $gray-900; }
    &.default { background: $gray-100; color: $gray-500; border: 1px solid $gray-200; }
}

/* skeleton */
.loader-rows { padding: 8px; }
.skeleton-row {
    height: 42px; background: $gray-100;
    margin-bottom: 6px; animation: pulse 1.6s infinite ease-in-out;
}
.empty-cell { text-align: center; padding: 60px 0; color: $gray-400; font-size: 0.88rem; }

/* Mobile list */
.mobile-list { display: none; @media (max-width: 860px) { display: block; } }
.m-subtotal {
    display: flex; align-items: center; gap: 8px;
    background: $white; border: 1px solid $gray-200; padding: 10px 14px;
    margin-bottom: 10px; font-size: 0.82rem;
    .m-subtotal-label { font-weight: 700; color: $gray-900; }
    .m-subtotal-amt { color: $gray-700; margin-left: auto; }
    .num { font-weight: 700; }
}
.m-ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.m-li { background: $white; border: 1px solid $gray-200; padding: 14px; }
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
