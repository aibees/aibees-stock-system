<template>
    <div id="trade-profit">
        <BrandHeader :title="title" back="/trade" />

        <div class="contents">

            <!-- ── 상단 타이틀 ── -->
            <section class="head-desc">
                <div class="head-left">
                    <p class="sub-text">
                        매도로 <b>확정된 실현손익</b>입니다(수수료·제세금 차감 후).
                        보유 중인 종목의 평가손익은 <b>계좌 현황</b>에서 확인하세요.
                    </p>
                </div>
                <div class="head-right">
                    <button class="btn-refresh" :disabled="loading" @click="fetchData">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M23 4v6h-6" />
                            <path d="M1 20v-6h6" />
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10" />
                            <path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14" />
                        </svg>
                        {{ loading ? '조회 중…' : '새로고침' }}
                    </button>
                </div>
            </section>

            <!-- ── 조회 조건: 1줄 기간 / 2줄 시작일·종료일·조회 ── -->
            <section class="card query-card">
                <div class="seg full" role="group" aria-label="기간">
                    <button v-for="p in presets" :key="p.days" type="button"
                        :class="{ on: activePreset === p.days }" @click="applyPreset(p.days)">
                        {{ p.label }}
                    </button>
                </div>
                <div class="date-row">
                    <label class="df">
                        <span>시작일</span>
                        <input type="date" v-model="form.start" :max="form.end" />
                    </label>
                    <label class="df">
                        <span>종료일</span>
                        <input type="date" v-model="form.end" :min="form.start" :max="todayStr" />
                    </label>
                    <button class="btn-run" :disabled="loading" @click="fetchData">
                        {{ loading ? '조회 중…' : '조회' }}
                    </button>
                </div>
            </section>

            <!-- 오류 / 안내 -->
            <section v-if="errorMsg" class="card empty-card"><p>{{ errorMsg }}</p></section>
            <p v-if="truncated" class="warn-note">
                조회 결과가 많아 일부만 표시했습니다. 기간을 좁혀서 다시 조회해 주세요.
            </p>

            <!-- ── 표 (데스크톱) ── -->
            <section class="table-section">
                <div v-if="loading" class="loader-rows">
                    <div v-for="n in 6" :key="n" class="skeleton-row"></div>
                </div>
                <table v-else class="grid-table">
                    <thead>
                        <tr>
                            <th class="tl">매매일자</th>
                            <th class="tl">종목</th>
                            <th class="tr">매도수량</th>
                            <th class="tr">매입단가</th>
                            <th class="tr">매도단가</th>
                            <th class="tr">매도금액</th>
                            <th class="tr">실현손익</th>
                            <th class="tr">손익률</th>
                            <th class="tr">수수료</th>
                            <th class="tr">제세금</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="(row, i) in visibleRows" :key="`${row.trade_date}-${row.stock_code}-${i}`">
                            <td class="tl num">{{ row.trade_date }}</td>
                            <td class="tl">
                                <div class="stk">
                                    <span :class="['action-badge', sideClass(row)]">{{ sideLabel(row) }}</span>
                                    <span class="stk-name">{{ row.stock_name }}</span>
                                    <span class="stk-code">{{ row.stock_code }}</span>
                                </div>
                            </td>
                            <td class="tr num">{{ fmtQty(row.sell_qty) }}</td>
                            <td class="tr num">{{ fmtWon(row.buy_price) }}</td>
                            <td class="tr num">{{ fmtWon(row.sell_price) }}</td>
                            <td class="tr num">{{ fmtWon(row.sell_amount) }}</td>
                            <td class="tr num pnl" :class="pnlClass(row.realized_profit)">
                                {{ fmtSigned(row.realized_profit) }}
                            </td>
                            <td class="tr num pnl" :class="pnlClass(row.profit_rate)">{{ fmtPct(row.profit_rate) }}</td>
                            <td class="tr num">{{ fmtWon(row.fee) }}</td>
                            <td class="tr num">{{ fmtWon(row.tax) }}</td>
                        </tr>
                        <tr v-if="visibleRows.length === 0">
                            <td colspan="10" class="empty-cell">{{ emptyText }}</td>
                        </tr>
                    </tbody>
                    <tfoot v-if="visibleRows.length > 0">
                        <!-- 화면에 보이는 행의 소계: 이익 / 손실 / 총계 -->
                        <tr class="sub-row">
                            <td class="tl" colspan="6">이익 소계 <em class="cnt">{{ pnlSplit.gainCount }}건</em></td>
                            <td class="tr num pnl up">{{ fmtSigned(pnlSplit.gain) }}</td>
                            <td class="tr num" colspan="3"></td>
                        </tr>
                        <tr class="sub-row">
                            <td class="tl" colspan="6">손실 소계 <em class="cnt">{{ pnlSplit.lossCount }}건</em></td>
                            <td class="tr num pnl down">{{ fmtSigned(pnlSplit.loss) }}</td>
                            <td class="tr num" colspan="3"></td>
                        </tr>
                        <tr class="total-row">
                            <td class="tl" colspan="5">총계 <em class="cnt">{{ visibleRows.length }}건</em></td>
                            <td class="tr num">{{ fmtWon(pageTotals.sellAmount) }}</td>
                            <td class="tr num pnl" :class="pnlClass(pnlSplit.total)">{{ fmtSigned(pnlSplit.total) }}</td>
                            <td class="tr num"></td>
                            <td class="tr num">{{ fmtWon(pageTotals.fee) }}</td>
                            <td class="tr num">{{ fmtWon(pageTotals.tax) }}</td>
                        </tr>
                    </tfoot>
                </table>
            </section>

            <!-- ── 모바일 ── -->
            <section class="mobile-list">
                <div v-if="loading" class="loader-rows">
                    <div v-for="n in 3" :key="n" class="skeleton-row"></div>
                </div>
                <template v-else>
                    <div v-if="visibleRows.length > 0" class="m-summary">
                        <div class="ms-row">
                            <span class="ms-label">이익 소계 <em class="cnt">{{ pnlSplit.gainCount }}건</em></span>
                            <span class="num pnl up">{{ fmtSigned(pnlSplit.gain) }}</span>
                        </div>
                        <div class="ms-row">
                            <span class="ms-label">손실 소계 <em class="cnt">{{ pnlSplit.lossCount }}건</em></span>
                            <span class="num pnl down">{{ fmtSigned(pnlSplit.loss) }}</span>
                        </div>
                        <div class="ms-row total">
                            <span class="ms-label">총계 <em class="cnt">{{ visibleRows.length }}건</em></span>
                            <span class="num pnl" :class="pnlClass(pnlSplit.total)">{{ fmtSigned(pnlSplit.total) }}</span>
                        </div>
                    </div>
                    <ul class="m-ul">
                        <li v-for="(row, i) in visibleRows" :key="`m-${row.trade_date}-${row.stock_code}-${i}`"
                            class="m-li">
                            <div class="li-top">
                                <span :class="['action-badge', sideClass(row)]">{{ sideLabel(row) }}</span>
                                <span class="num pnl" :class="pnlClass(row.realized_profit)">
                                    {{ fmtSigned(row.realized_profit) }} ({{ fmtPct(row.profit_rate) }})
                                </span>
                            </div>
                            <div class="li-name">
                                {{ row.stock_name }}
                                <span class="stk-code">{{ row.stock_code }}</span>
                            </div>
                            <div class="li-row"><span class="li-label">매매일자</span><span>{{ row.trade_date }}</span></div>
                            <div class="li-row"><span class="li-label">매도수량</span><span>{{ fmtQty(row.sell_qty) }}</span></div>
                            <div class="li-row">
                                <span class="li-label">매입/매도</span>
                                <span>{{ fmtWon(row.buy_price) }} / {{ fmtWon(row.sell_price) }}</span>
                            </div>
                            <div class="li-row"><span class="li-label">매도금액</span><span>{{ fmtWon(row.sell_amount) }} 원</span></div>
                            <div class="li-row">
                                <span class="li-label">수수료/세금</span>
                                <span>{{ fmtWon(row.fee) }} / {{ fmtWon(row.tax) }}</span>
                            </div>
                        </li>
                        <li v-if="visibleRows.length === 0" class="empty-cell">{{ emptyText }}</li>
                    </ul>
                </template>
            </section>

        </div>
    </div>
</template>

<script setup>
// 매매손익 API 는 py-naver-stock-theme(ROOT 서버, API_SERVER_URL) 소관이라
// batchApi(py-stock-batch) 가 아니라 aibeesApi 를 쓴다. 이 엔드포인트는
// @require_auth 로 보호되므로 Authorization 헤더가 실려야 하는데, aibeesApi 의
// request interceptor 가 Bearer 토큰을 붙여준다(aibeesApi.js 참고).
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores';

const title = ref('매매손익');

const userSession = assUserSession();
const userId = computed(() => {
    const uid = userSession.user?.loginInfo?.user_id;
    return uid ? Number(uid) : null;
});

/* ── 조회 조건 ── */
const toDateStr = (d) => {
    // toISOString() 은 UTC 로 바꿔버려서 KST 오전 9시 이전엔 하루 전 날짜가 나온다.
    const z = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
};
const todayStr = toDateStr(new Date());
const daysAgoStr = (days) => {
    const d = new Date();
    d.setDate(d.getDate() - days);
    return toDateStr(d);
};

const presets = [
    { days: 0, label: '오늘' },
    { days: 7, label: '1주' },
    { days: 30, label: '1개월' },
    { days: 90, label: '3개월' },
];

const form = reactive({ start: daysAgoStr(30), end: todayStr });

// 프리셋 버튼 활성 표시 — 날짜를 직접 고치면 어떤 프리셋과도 안 맞으므로 null.
const activePreset = computed(() => {
    if (form.end !== todayStr) return null;
    const p = presets.find(p => daysAgoStr(p.days) === form.start);
    return p ? p.days : null;
});

const applyPreset = (days) => {
    form.start = daysAgoStr(days);
    form.end = todayStr;
    fetchData();
};

/* ── 상태 ── */
const rows = ref([]);
const truncated = ref(false);
const loading = ref(true);
const errorMsg = ref('');
const loaded = ref(false);

const fetchData = async () => {
    if (!userId.value) {
        errorMsg.value = '로그인 세션이 없습니다. 다시 로그인해 주세요.';
        loading.value = false;
        return;
    }
    loading.value = true;
    errorMsg.value = '';
    try {
        const { data } = await aibeesApi.get('/api/v1/profit/trade-profit', {
            // user_id 는 보내지 않는다 — 서버가 JWT(g.current_user_id)로 대상 유저를
            // 결정한다. 보내더라도 JWT 와 다르면 403 으로 거절된다(router_profit.py).
            params: {
                start: form.start,
                end: form.end,
            },
        });
        rows.value = data?.data?.rows ?? [];
        truncated.value = !!data?.data?.truncated;
        loaded.value = true;
    } catch (e) {
        // 서버가 내려준 안내 문구(KIS 키 미등록 등)를 그대로 보여주는 게 가장 친절하다.
        // py-naver-stock-theme 의 ApiResponse.error 는 { error: { message } } 포맷이다
        // (py-stock-batch 는 { message } — 엔드포인트 이전 이력이 있어 둘 다 받아준다).
        errorMsg.value = e?.response?.data?.error?.message
            || e?.response?.data?.message
            || '매매손익 조회에 실패했습니다.';
        rows.value = [];
        truncated.value = false;
    } finally {
        loading.value = false;
    }
};

onMounted(fetchData);

/* ── 표시용 가공 ── */
const visibleRows = computed(() => rows.value);

const emptyText = computed(() => {
    if (errorMsg.value) return '조회에 실패했습니다.';
    if (!loaded.value) return '조회 조건을 선택해 주세요.';
    return '해당 기간에 매매 내역이 없습니다.';
});

// 화면에 보이는 행의 이익/손실 분리 소계. 총계 = 이익 + 손실(= 순 실현손익).
// 손익이 0 이거나 없는 행은 어느 쪽에도 넣지 않는다(건수 합이 전체 건수보다 작을 수 있다).
const pnlSplit = computed(() => {
    let gain = 0, loss = 0, gainCount = 0, lossCount = 0;
    for (const r of visibleRows.value) {
        const v = toNum(r.realized_profit);
        if (v === null || Number.isNaN(v) || v === 0) continue;
        if (v > 0) { gain += v; gainCount += 1; }
        else { loss += v; lossCount += 1; }
    }
    return { gain, loss, gainCount, lossCount, total: gain + loss };
});

// 화면에 보이는 행의 합계(매도금액·수수료·제세금).
const pageTotals = computed(() => {
    let sellAmount = 0, profit = 0, fee = 0, tax = 0;
    for (const r of visibleRows.value) {
        sellAmount += toNum(r.sell_amount) ?? 0;
        profit += toNum(r.realized_profit) ?? 0;
        fee += toNum(r.fee) ?? 0;
        tax += toNum(r.tax) ?? 0;
    }
    return { sellAmount, profit, fee, tax };
});

/* ── 헬퍼 (MyWallet.vue 와 동일 규칙) ── */
const toNum = (v) => (v === null || v === undefined || v === '') ? null : Number(v);

const fmtWon = (v) => {
    const n = toNum(v);
    return n === null || Number.isNaN(n) ? '-' : n.toLocaleString(undefined, { maximumFractionDigits: 0 });
};
const fmtQty = (v) => {
    const n = toNum(v);
    return n === null || Number.isNaN(n) ? '-' : n.toLocaleString(undefined, { maximumFractionDigits: 0 });
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
// 매수/매도 구분(뱃지). 매도 수량이 있으면 매도, 아니면 매수만 있었던 날이다.
const sideLabel = (row) => (Number(row.sell_qty) > 0 ? '매도' : '매수');
const sideClass = (row) => (Number(row.sell_qty) > 0 ? 'sell' : 'buy');

// 국내 관례: 이익=적색, 손실=청색
const pnlClass = (v) => {
    const n = toNum(v);
    if (n === null || n === 0) return '';
    return n > 0 ? 'up' : 'down';
};
</script>

<style scoped lang="scss">
// 무채색 팔레트(MyWallet / trade 대시보드와 통일).
$white: #ffffff;
$gray-50: #FFFBEA;
$gray-100: #F3EAD2;
$gray-200: #EFE2BC;
$gray-300: #E3D3A8;
$gray-400: #9A8C7E;
$gray-500: #6B5B4E;
$gray-700: #4A3628;
$gray-900: #2B1D14;
$blue: #1F5BD1;
$accent: #7A4423;
$navy: #74462A;
$red: #C8282A;
$green: #1F7A3E;

#trade-profit {
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
    .sub-text { font-size: 0.82rem; color: $gray-500; margin: 6px 0 0; line-height: 1.5; text-align: left; }

    @media (max-width: 600px) { flex-direction: column; align-items: flex-start; gap: 12px; }
}

.btn-refresh {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 16px; background: $navy; color: $white; border: none;
    font-size: 0.84rem; font-weight: 600; cursor: pointer;
    font-family: inherit; transition: background .15s;
    &:hover:not(:disabled) { background: #74462A; }
    &:disabled { background: $gray-400; cursor: default; }
}

/* 조회 조건 */
.card {
    border-radius: 12px;
    background: $white; border: 1px solid $gray-200;
    padding: 16px; margin-bottom: 16px;
}
.empty-card p { margin: 0; color: $gray-500; font-size: 0.86rem; }

.query-card { display: flex; flex-direction: column; gap: 12px; }
// 데스크톱에서는 조회 영역이 화면 전체로 늘어나지 않게 폭을 제한한다
@media (min-width: 640px) { .query-card { max-width: 520px; } }
.seg.full {
    display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); width: 100%; box-sizing: border-box;
    button { padding: 10px 0; }
}
.date-row { display: flex; align-items: flex-end; gap: 6px; }
.df {
    flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px;
    span { font-size: 0.74rem; font-weight: 700; color: $gray-500; letter-spacing: .03em; }
    input {
        width: 100%; min-width: 0; box-sizing: border-box; border-radius: 12px;
        padding: 8px 6px; border: 1px solid $gray-300; background: $white;
        font-size: 0.84rem; font-family: inherit; color: $gray-900;
        &:focus { outline: none; border-color: $gray-900; }
    }
}
// App.vue 의 모바일 전역 규칙(#app input → 16px, iOS 확대 방지)은 한 줄에 날짜 2개 + 버튼을 넣기엔 너무 커서
// 이 화면의 날짜 입력만 id 로 우선순위를 높여 줄인다(날짜 입력은 키보드가 아니라 선택기가 열린다).
#trade-profit .df input {
    font-size: 13px;
    padding: 6px 2px 6px 5px;     // 좌우 여백을 최소로 — 글자와 달력 아이콘이 겹치지 않게
    letter-spacing: -0.3px;
    text-align: left;
    -webkit-appearance: none;
    appearance: none;
}
// 브라우저가 날짜 입력 내부(연·월·일 필드, 구분자)에 넣는 기본 여백도 걷어낸다
#trade-profit .df input::-webkit-datetime-edit,
#trade-profit .df input::-webkit-datetime-edit-fields-wrapper { padding: 0; }
#trade-profit .df input::-webkit-datetime-edit-text { padding: 0; margin: 0 1px 0 0; }
#trade-profit .df input::-webkit-datetime-edit-year-field,
#trade-profit .df input::-webkit-datetime-edit-month-field,
#trade-profit .df input::-webkit-datetime-edit-day-field { padding: 0; }
#trade-profit .df input::-webkit-date-and-time-value { text-align: left; margin: 0; min-height: 1em; }
// 달력 아이콘: 크기·여백을 줄여 글자 쪽 폭을 확보한다
#trade-profit .df input::-webkit-calendar-picker-indicator {
    width: 12px; height: 12px; padding: 0; margin: 0 3px 0 0;
}
.seg {
    border-radius: 12px;
    display: inline-flex; border: 1px solid $gray-300; overflow: hidden;
    button {
        padding: 7px 12px; background: $white; border: none; cursor: pointer;
        font-size: 0.8rem; font-weight: 600; color: $gray-500; font-family: inherit;
        border-right: 1px solid $gray-200;
        &:last-child { border-right: none; }
        &.on { background: #74462A; color: $white; }
    }
}
.btn-run {
    flex-shrink: 0; height: 36px; padding: 0 12px; border-radius: 12px; background: $navy; color: $white; border: none;
    font-size: 0.84rem; font-weight: 700; cursor: pointer; font-family: inherit;
    &:hover:not(:disabled) { background: #74462A; }
    &:disabled { background: $gray-400; cursor: default; }
}
.warn-note {
    border-radius: 12px;
    background: $gray-100; border: 1px solid $gray-300;
    padding: 10px 14px; margin: 0 0 16px; font-size: 0.8rem; color: $gray-700;
}

/* Table */
.table-section {
    border-radius: 12px;
    background: $white; border: 1px solid $gray-200; overflow-x: auto;
    @media (max-width: 860px) { display: none; }
}
.grid-table {
    width: 100%; border-collapse: collapse; font-size: 0.84rem;

    thead tr { border-bottom: 1px solid $gray-200; background: $gray-50; }
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

    .up { color: $red; }
    .down { color: $blue; }

    tfoot .sub-row td { background: $gray-50; border-top: 1px solid $gray-100; color: $gray-700; font-weight: 600; }
    tfoot .total-row td {
        background: $gray-50; font-weight: 700; color: #74462A;
        border-top: 2px solid $gray-200;
    }
}

.stk { display: flex; align-items: center; gap: 8px; }
.stk-name { color: $gray-900; font-weight: 600; }
// 종목코드: 뱃지가 아니라 종목명 옆에 작게
.stk-code { font-size: 0.72rem; color: $gray-400; font-variant-numeric: tabular-nums; }
// 매수/매도 뱃지(글자로도 구분된다)
.action-badge {
    font-size: 0.7rem; font-weight: 700; padding: 2px 8px; white-space: nowrap; border-radius: 12px;
    &.sell { background: #E8F0FE; color: $blue; border: 1px solid #C9DAFB; }
    &.buy  { background: #FDECEC; color: $red;  border: 1px solid #F6CFCF; }
}
// 손익 금액·%: 굵게, 글자는 살짝 작게
.pnl { font-weight: 700; font-size: 0.92em; }

/* skeleton */
.loader-rows { padding: 8px; }
.skeleton-row {
    height: 42px; background: $gray-100;
    margin-bottom: 6px; animation: pulse 1.6s infinite ease-in-out;
}
.empty-cell { text-align: center; padding: 60px 0; color: $gray-400; font-size: 0.88rem; }

/* Mobile list */
.mobile-list { display: none; @media (max-width: 860px) { display: block; } }
.m-summary {
    border-radius: 12px;
    background: $white; border: 1px solid $gray-200; padding: 4px 14px;
    margin-bottom: 10px; font-size: 0.84rem;
    .ms-row { display: flex; align-items: center; justify-content: space-between; min-height: 38px; border-top: 1px solid $gray-100; }
    .ms-row:first-child { border-top: none; }
    .ms-label { color: $gray-700; font-weight: 600; }
    .ms-row.total { border-top: 1.5px solid $gray-300; .ms-label { color: $gray-900; font-weight: 700; } }
}
.cnt { font-style: normal; font-weight: 500; font-size: 0.74rem; color: $gray-400; margin-left: 4px; }
.m-ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.m-li { background: $white; border: 1px solid $gray-200; padding: 14px; border-radius: 12px; }
.li-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.li-name {
    display: flex; align-items: center; gap: 8px;
    font-size: 0.95rem; font-weight: 700; color: $gray-900; margin-bottom: 8px;
}
.li-row {
    display: flex; gap: 8px; font-size: 0.8rem; margin-bottom: 4px; color: $gray-700;
    .li-label { flex-shrink: 0; width: 84px; color: $gray-500; font-weight: 600; }
}
.up { color: $red; }
.down { color: $blue; }

@keyframes pulse { 0%, 100% { opacity: .5; } 50% { opacity: .9; } }

/* 안쪽 제목을 걷어내고 버튼만 남았으므로 오른쪽 끝에 둔다(헤더에 이미 제목이 있다) */
.head-desc .head-right { margin-left: auto; }
</style>
