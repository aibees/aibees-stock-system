<template>
    <div id="trade-simulation">
        <Headers :prop_title="title" />

        <div class="contents">

            <!-- ── 상단 ── -->
            <section class="head-desc">
                <div class="head-left">
                    <h2>내 설정 시뮬레이션</h2>
                    <p class="sub-text">
                        지금 저장된 <b>내 worker 설정</b>으로 과거 매수추천을 되짚어 매매했다면
                        어떤 결과였을지 계산합니다.
                    </p>
                </div>
            </section>

            <!-- ══════════ 1. 내 worker 설정 요약 ══════════ -->
            <section class="card cfg-card">
                <header class="card-head">
                    <h3>내 worker 설정</h3>
                    <span class="hint-text">이 값으로 시뮬을 돌립니다</span>
                </header>

                <div v-if="cfgLoading" class="skeleton-box"></div>

                <template v-else>
                    <!-- 매수 -->
                    <div class="cfg-group">
                        <span class="cfg-group-title">
                            매수 — 후보 우선순위
                            <button type="button" class="btn-link" @click="goBuySetting">변경</button>
                        </span>
                        <div class="order-chips">
                            <template v-for="(s, i) in appliedOrder" :key="s.field">
                                <span class="ord-chip">
                                    <b>{{ i + 1 }}</b>
                                    {{ ORDER_LABEL[s.field] ?? s.field }}
                                    <i>{{ s.desc ? '↓' : '↑' }}</i>
                                </span>
                                <span v-if="i < appliedOrder.length - 1" class="ord-arrow">→</span>
                            </template>
                            <span v-if="cfg.buy?.is_default" class="badge-default">기본값</span>
                        </div>
                        <p class="cfg-note">
                            같은 날 추천 중 <b>1순위 종목</b>을 매수합니다.
                            앞 기준이 동점일 때만 다음 기준으로 넘어갑니다.
                        </p>
                    </div>

                    <!-- 매도 -->
                    <div class="cfg-group">
                        <span class="cfg-group-title">
                            매도 — 청산 조건
                            <button type="button" class="btn-link" @click="goSellSetting">변경</button>
                        </span>
                        <div class="cfg-grid">
                            <div v-for="f in cfg.sell" :key="f.key"
                                :class="['cfg-item', { off: isOff(f) }]">
                                <span class="ci-label">{{ f.label }}</span>
                                <span class="ci-value">
                                    {{ fmtCfg(f) }}
                                    <span v-if="f.is_default" class="badge-default sm">기본</span>
                                </span>
                            </div>
                        </div>
                    </div>
                </template>
            </section>

            <!-- ══════════ 2. 실행 조건 ══════════ -->
            <section class="card run-card">
                <header class="card-head"><h3>시뮬 조건</h3></header>

                <div class="run-form">
                    <label class="rf-field">
                        <span>시작일</span>
                        <input type="date" v-model="form.start_date" />
                    </label>
                    <label class="rf-field">
                        <span>종료일</span>
                        <input type="date" v-model="form.end_date" />
                    </label>
                    <label class="rf-field">
                        <span>초기 자금</span>
                        <input type="number" v-model.number="form.init_cash" step="100000" min="100000" />
                    </label>
                    <div class="rf-field">
                        <span>매수 체결</span>
                        <div class="seg">
                            <button type="button" :class="{ on: form.entry_price === 'next_open' }"
                                @click="form.entry_price = 'next_open'">다음날 시가</button>
                            <button type="button" :class="{ on: form.entry_price === 'close' }"
                                @click="form.entry_price = 'close'">추천일 종가</button>
                        </div>
                    </div>
                    <label class="rf-check" :class="{ disabled: form.entry_price !== 'next_open' }">
                        <input type="checkbox" v-model="form.skip_gapup"
                            :disabled="form.entry_price !== 'next_open'" />
                        <span>갭업이면 매수 안 함</span>
                    </label>
                    <button class="btn-run" :disabled="isRunning || !form.start_date" @click="runSim">
                        {{ isRunning ? '계산 중…' : '시뮬 실행' }}
                    </button>
                </div>
                <p class="run-note">
                    매수 체결가는 현실성을 위해 <b>다음 거래일 시가</b>가 기본입니다.
                    추천일 종가는 그날 장 마감 후 추천이 나오므로 실제로는 체결할 수 없는 가격입니다.
                </p>
                <p v-if="errorMsg" class="run-error">{{ errorMsg }}</p>
            </section>

            <!-- ══════════ 3. 결과 ══════════ -->
            <template v-if="result">
                <section v-if="!result.ok" class="card empty-card">
                    <p>{{ result.message }}</p>
                </section>

                <template v-else>
                    <!-- 요약 -->
                    <section class="card sum-card">
                        <header class="card-head">
                            <h3>결과 요약</h3>
                            <span class="period-badge">
                                {{ result.period.start }} ~ {{ result.period.end }}
                                ({{ result.period.trading_days }}거래일)
                            </span>
                        </header>

                        <div class="final-row" :class="pnlClass(result.final.pnl)">
                            <span class="fr-label">최종 자산</span>
                            <span class="fr-value">{{ won(result.final.final_cash) }}</span>
                            <span class="fr-delta">
                                {{ result.final.pnl >= 0 ? '+' : '' }}{{ won(result.final.pnl) }}
                                ({{ result.final.pnl_pct >= 0 ? '+' : '' }}{{ result.final.pnl_pct }}%)
                            </span>
                            <span class="fr-init">시작 {{ won(result.final.init_cash) }}</span>
                        </div>

                        <div class="stat-grid">
                            <div class="stat"><span>매매</span><b>{{ result.summary.trades }}건</b></div>
                            <div class="stat"><span>승률</span><b>{{ result.summary.win_rate }}%</b></div>
                            <div class="stat"><span>평균 수익</span>
                                <b :class="pnlClass(result.summary.avg_ret)">{{ result.summary.avg_ret }}%</b></div>
                            <div class="stat"><span>평균 이익</span>
                                <b class="up">{{ result.summary.avg_win }}%</b></div>
                            <div class="stat"><span>평균 손실</span>
                                <b class="down">{{ result.summary.avg_loss }}%</b></div>
                            <div class="stat"><span>손익비(PF)</span><b>{{ result.summary.profit_factor }}</b></div>
                            <div class="stat"><span>최대낙폭</span>
                                <b class="down">{{ result.summary.mdd }}%</b></div>
                            <div class="stat"><span>평균 보유</span><b>{{ result.summary.avg_bars }}봉</b></div>
                        </div>

                        <div v-if="exitBreakdown.length" class="exit-row">
                            <span class="er-label">청산 사유</span>
                            <span v-for="e in exitBreakdown" :key="e.key" class="er-chip">
                                {{ e.label }} <b>{{ e.count }}</b>
                            </span>
                        </div>
                    </section>

                    <!-- 잔액 곡선 -->
                    <section v-if="result.equity_curve.length > 1" class="card chart-card">
                        <header class="card-head"><h3>자산 추이</h3></header>
                        <div class="chart-box"><canvas ref="equityCanvas"></canvas></div>
                    </section>

                    <!-- 매매 로그 -->
                    <section class="card log-card">
                        <header class="card-head">
                            <h3>매매 로그</h3>
                            <span class="hint-text">{{ result.trades.length }}건</span>
                        </header>

                        <div v-if="!result.trades.length" class="empty-inline">
                            조건에 맞는 매매가 없었습니다.
                        </div>
                        <div v-else class="table-wrap">
                            <table class="log-table">
                                <thead>
                                    <tr>
                                        <th class="tc">#</th>
                                        <th>종목</th>
                                        <th>매수일</th>
                                        <th class="tr">매수가</th>
                                        <th>매도일</th>
                                        <th class="tr">매도가</th>
                                        <th class="tc">사유</th>
                                        <th class="tc">봉</th>
                                        <th class="tr">손익</th>
                                        <th class="tr">잔액</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="(t, i) in result.trades" :key="i"
                                        :class="t.ret_net_pct > 0 ? 'win' : 'lose'">
                                        <td class="tc">{{ i + 1 }}</td>
                                        <td class="name-cell">
                                            <b>{{ t.stock_name || t.coin }}</b>
                                            <i>{{ t.coin }}</i>
                                        </td>
                                        <td>{{ t.entry_dt }}</td>
                                        <td class="tr num">{{ num(t.entry_price) }}</td>
                                        <td>{{ t.exit_dt }}</td>
                                        <td class="tr num">{{ num(t.exit_price) }}</td>
                                        <td class="tc"><span class="reason">{{ t.exit_reason_kr }}</span></td>
                                        <td class="tc num">{{ t.bars_held }}</td>
                                        <td class="tr num" :class="pnlClass(t.ret_net_pct)">
                                            {{ t.ret_net_pct >= 0 ? '+' : '' }}{{ t.ret_net_pct }}%
                                        </td>
                                        <td class="tr num">{{ won(t.cash_after) }}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <p class="log-note">
                            손익은 왕복 수수료·세금 {{ (result.config.fee_rate * 200).toFixed(2) }}%를 뺀 값입니다.
                            적용 정렬: <code>{{ result.config.buy_order }}</code>
                        </p>
                    </section>
                </template>
            </template>
        </div>
    </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import Chart from 'chart.js/auto';
import aibeesApi from '@scripts/aibeesApi.js';
import mariaToast from '@scripts/mariaToast.js';

const title = ref('시뮬레이션');
const router = useRouter();

const ORDER_LABEL = {
    score: '추천점수', volume: '거래량', rate: '등락률',
    rank_no: '추천순위', close: '종가',
};

/* ═══════════ 1. worker 설정 요약 ═══════════ */
const cfg = reactive({ buy: null, sell: [] });
const cfgLoading = ref(true);

const fetchConfig = async () => {
    cfgLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/strategy/worker-config');
        cfg.buy = data.data?.buy ?? null;
        cfg.sell = data.data?.sell ?? [];
    } catch (e) {
        console.error('[TradeSimulation] 설정 조회 실패', e);
    } finally {
        cfgLoading.value = false;
    }
};

// "volume:desc,score:desc" → [{field:'volume',desc:true}, ...]
const appliedOrder = computed(() => {
    const spec = cfg.buy?.applied || '';
    return spec.split(',').filter(Boolean).map(t => {
        const [f, d] = t.split(':');
        return { field: f.trim(), desc: (d || '').trim() !== 'asc' };
    });
});

/** 값이 null 이면 전략 기본값이 적용되므로 default 를 대신 표시한다. */
const cfgVal = (f) => (f.value === null || f.value === undefined ? f.default : f.value);

const isOff = (f) => f.type === 'bool' && Number(cfgVal(f)) !== 1;

const fmtCfg = (f) => {
    const v = cfgVal(f);
    if (v === null || v === undefined) return '미사용';
    if (f.type === 'bool') return Number(v) === 1 ? '사용' : '미사용';
    if (f.type === 'pct') return `${+(Number(v) * 100).toFixed(2)}%`;
    if (f.type === 'bars') return `${v}봉`;
    return String(v);
};

// master_menu 의 menu_path 기준 경로 (menu_parents=Trade + menu_path)
//   TradeBuySetting  → trade-buy-setting
//   TradeSetting     → trade-sell-setting
const goBuySetting = () => router.push({ path: '/trade/trade-buy-setting' });
const goSellSetting = () => router.push({ path: '/trade/trade-sell-setting' });

/* ═══════════ 2. 시뮬 실행 ═══════════ */
const iso = (d) => d.toISOString().slice(0, 10);
const today = new Date();
const threeMonthsAgo = new Date(today.getTime() - 90 * 86400000);

const form = reactive({
    start_date: iso(threeMonthsAgo),
    end_date: iso(today),
    init_cash: 1000000,
    entry_price: 'next_open',
    skip_gapup: false,
});

const result = ref(null);
const isRunning = ref(false);
const errorMsg = ref('');

const runSim = async () => {
    if (form.end_date && form.end_date < form.start_date) {
        errorMsg.value = '종료일이 시작일보다 앞설 수 없습니다.';
        return;
    }
    isRunning.value = true;
    errorMsg.value = '';
    try {
        const { data } = await aibeesApi.post('/api/v1/strategy/sim/buy-target', { ...form });
        result.value = data.data;
        if (result.value?.ok) {
            await nextTick();
            drawChart();
            mariaToast.success(`매매 ${result.value.summary.trades}건 · ${result.value.final.pnl_pct}%`);
        }
    } catch (e) {
        console.error('[TradeSimulation] 시뮬 실패', e);
        errorMsg.value = e?.response?.data?.error?.message || '시뮬레이션에 실패했습니다.';
    } finally {
        isRunning.value = false;
    }
};

const exitBreakdown = computed(() => {
    const b = result.value?.summary?.exit_breakdown ?? {};
    const KR = {
        SELL_PROFIT: '익절', SELL_STOP_LOSS: '손절', SELL_STOP_PROFIT: '익절',
        SELL_TRAIL: '트레일링', SELL_TIME: '타임스탑', EOD: '기간종료',
    };
    return Object.entries(b).map(([k, v]) => ({ key: k, label: KR[k] ?? k, count: v }));
});

/* ═══════════ 3. 자산 추이 차트 ═══════════ */
const equityCanvas = ref(null);
let chart = null;

const drawChart = () => {
    if (!equityCanvas.value || !result.value?.equity_curve) return;
    if (chart) { chart.destroy(); chart = null; }

    const curve = result.value.equity_curve;
    const init = result.value.final.init_cash;

    chart = new Chart(equityCanvas.value, {
        type: 'line',
        data: {
            labels: curve.map(p => p.label),
            datasets: [{
                label: '자산',
                data: curve.map(p => p.cash),
                borderColor: '#1971c2',
                backgroundColor: 'rgba(25,113,194,.10)',
                fill: { target: { value: init } },
                borderWidth: 2,
                pointRadius: 3,
                pointBackgroundColor: curve.map(p => (p.cash >= init ? '#2f9e44' : '#e03131')),
                tension: 0.15,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (c) => ` ${c.parsed.y.toLocaleString()}원`,
                    },
                },
            },
            scales: {
                y: {
                    ticks: { callback: (v) => `${(v / 10000).toLocaleString()}만` },
                    grid: { color: 'rgba(0,0,0,.06)' },
                },
                x: { ticks: { maxRotation: 60, minRotation: 0, font: { size: 10 } }, grid: { display: false } },
            },
        },
    });
};

onBeforeUnmount(() => { if (chart) chart.destroy(); });
onMounted(fetchConfig);

/* ═══════════ 포맷 ═══════════ */
const won = (v) => (v === null || v === undefined ? '-' : Math.round(Number(v)).toLocaleString() + '원');
const num = (v) => (v === null || v === undefined ? '-' : Math.round(Number(v)).toLocaleString());
const pnlClass = (v) => (Number(v) > 0 ? 'up' : Number(v) < 0 ? 'down' : '');
</script>

<style scoped>
#trade-simulation { min-height: 100vh; background: #f4f6f9; }

.contents {
    max-width: 980px;
    margin: 0 auto;
    padding: 16px 14px 96px;
    box-sizing: border-box;
}

.head-desc { padding: 8px 4px 16px; }
.head-desc h2 { margin: 0; text-align: start; font-size: 1.25rem; font-weight: 700; color: #1f2329; }
.head-desc .sub-text { margin: 6px 0 0; font-size: 0.85rem; color: #6b7280; line-height: 1.45; }

.card {
    background: #fff;
    border: 1px solid #e5e9ef;
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 14px;
}

.card-head {
    display: flex; align-items: center; justify-content: space-between;
    gap: 10px; margin-bottom: 12px;
}
.card-head h3 { margin: 0; font-size: 0.98rem; font-weight: 700; color: #1f2329; }
.ch-right { display: flex; align-items: center; gap: 10px; }
.hint-text { font-size: 0.72rem; color: #adb5bd; }

.btn-link {
    border: none; background: none; padding: 0;
    color: #1971c2; font-size: 0.75rem; font-weight: 600; cursor: pointer;
    text-decoration: underline;
}

.skeleton-box {
    height: 120px; border-radius: 10px;
    background: linear-gradient(90deg, #eceff3 25%, #f5f7fa 37%, #eceff3 63%);
    background-size: 400% 100%; animation: sk 1.2s ease infinite;
}
@keyframes sk { 0% { background-position: 100% 50%; } 100% { background-position: 0 50%; } }

/* ── 설정 요약 ── */
.cfg-group { padding: 12px 0; border-top: 1px solid #f1f3f5; }
.cfg-group:first-of-type { border-top: none; padding-top: 4px; }

.cfg-group-title {
    display: flex; align-items: center; gap: 9px; margin-bottom: 9px;
    font-size: 0.78rem; font-weight: 700; color: #495057;
}

.order-chips { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; }

.ord-chip {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 5px 11px; border-radius: 999px;
    background: #e7f0fd; color: #1971c2;
    font-size: 0.78rem; font-weight: 600;
}
.ord-chip b {
    width: 16px; height: 16px; border-radius: 50%;
    background: #1971c2; color: #fff;
    font-size: 0.62rem; display: inline-flex; align-items: center; justify-content: center;
}
.ord-chip i { font-style: normal; opacity: .75; }
.ord-arrow { color: #ced4da; font-size: 0.8rem; }

.badge-default {
    padding: 2px 8px; border-radius: 999px;
    background: #f1f3f5; color: #868e96;
    font-size: 0.68rem; font-weight: 600;
}
.badge-default.sm { margin-left: 5px; font-size: 0.62rem; padding: 1px 6px; }

.cfg-note { margin: 9px 0 0; font-size: 0.73rem; color: #868e96; line-height: 1.5; }

.cfg-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(178px, 1fr));
    gap: 7px;
}

.cfg-item {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    padding: 8px 11px; border-radius: 9px; background: #f8f9fb;
}
.cfg-item.off { opacity: .5; }
.ci-label { font-size: 0.75rem; color: #6b7280; }
.ci-value { font-size: 0.79rem; font-weight: 700; color: #1f2329; white-space: nowrap; }

/* ── 실행 조건 ── */
.run-form { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 10px; }

.rf-field { display: flex; flex-direction: column; gap: 5px; }
.rf-field > span { font-size: 0.72rem; font-weight: 600; color: #868e96; }
.rf-field input {
    height: 34px; padding: 0 10px;
    border: 1px solid #dee2e6; border-radius: 8px;
    font-size: 0.8rem; color: #1f2329; box-sizing: border-box;
}
.rf-field input[type="number"] { width: 130px; text-align: right; }

.seg { display: flex; gap: 4px; }
.seg button {
    height: 34px; padding: 0 12px;
    border: 1px solid #dee2e6; border-radius: 8px; background: #fff;
    color: #868e96; font-size: 0.76rem; font-weight: 600; cursor: pointer; white-space: nowrap;
}
.seg button.on { border-color: #1971c2; background: #e7f0fd; color: #1971c2; }

.rf-check {
    display: flex; align-items: center; gap: 6px; height: 34px;
    font-size: 0.76rem; color: #495057; cursor: pointer;
}
.rf-check.disabled { opacity: .4; cursor: not-allowed; }

.btn-run {
    height: 34px; padding: 0 22px; margin-left: auto;
    border: none; border-radius: 8px; background: #1971c2; color: #fff;
    font-size: 0.82rem; font-weight: 700; cursor: pointer; white-space: nowrap;
}
.btn-run:disabled { background: #ced4da; cursor: not-allowed; }

.run-note { margin: 11px 0 0; font-size: 0.72rem; color: #868e96; line-height: 1.5; }
.run-error { margin: 8px 0 0; font-size: 0.75rem; color: #e03131; font-weight: 600; }

/* ── 결과 요약 ── */
.period-badge {
    padding: 3px 10px; border-radius: 999px;
    background: #f1f3f5; color: #6b7280; font-size: 0.7rem; font-weight: 600;
}

.final-row {
    display: flex; align-items: baseline; flex-wrap: wrap; gap: 10px;
    padding: 14px 16px; border-radius: 11px; background: #f8f9fb; margin-bottom: 12px;
}
.final-row.up { background: #fff5f5; }
.final-row.down { background: #eef6ff; }
.fr-label { font-size: 0.75rem; color: #868e96; font-weight: 600; }
.fr-value { font-size: 1.32rem; font-weight: 800; color: #1f2329; }
.fr-delta { font-size: 0.92rem; font-weight: 700; }
.final-row.up .fr-delta { color: #e03131; }
.final-row.down .fr-delta { color: #1971c2; }
.fr-init { margin-left: auto; font-size: 0.72rem; color: #adb5bd; }

.stat-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(104px, 1fr)); gap: 7px;
}
.stat {
    display: flex; flex-direction: column; gap: 3px;
    padding: 9px 11px; border-radius: 9px; background: #f8f9fb;
}
.stat span { font-size: 0.7rem; color: #868e96; }
.stat b { font-size: 0.92rem; color: #1f2329; }

.exit-row {
    display: flex; align-items: center; flex-wrap: wrap; gap: 6px;
    margin-top: 12px; padding-top: 12px; border-top: 1px solid #f1f3f5;
}
.er-label { font-size: 0.72rem; font-weight: 700; color: #868e96; }
.er-chip {
    padding: 3px 10px; border-radius: 999px; background: #f1f3f5;
    font-size: 0.73rem; color: #495057;
}
.er-chip b { color: #1971c2; }

/* ── 차트 ── */
.chart-box { height: 280px; position: relative; }

/* ── 매매 로그 ── */
.table-wrap { overflow-x: auto; }
.log-table { width: 100%; border-collapse: collapse; font-size: 0.76rem; white-space: nowrap; }
.log-table th {
    padding: 8px; background: #f8f9fb; border-bottom: 1px solid #e5e9ef;
    color: #868e96; font-weight: 600; text-align: left;
}
.log-table td { padding: 9px 8px; border-bottom: 1px solid #f1f3f5; color: #343a40; }
.log-table tr.win td { background: #fffafa; }
.log-table tr.lose td { background: #f7fbff; }
.log-table .tr { text-align: right; }
.log-table .tc { text-align: center; }
.log-table .num { font-variant-numeric: tabular-nums; }

.name-cell b { display: block; font-weight: 600; color: #1f2329; }
.name-cell i { font-style: normal; font-size: 0.68rem; color: #adb5bd; }

.reason {
    padding: 2px 8px; border-radius: 999px;
    background: #f1f3f5; color: #495057; font-size: 0.7rem; font-weight: 600;
}

.up { color: #e03131; }
.down { color: #1971c2; }

.log-note { margin: 10px 0 0; font-size: 0.71rem; color: #868e96; line-height: 1.5; }
.log-note code { color: #1971c2; }

.empty-card, .empty-inline {
    text-align: center; color: #868e96; font-size: 0.82rem; padding: 22px 0;
}
.empty-card p { margin: 0; line-height: 1.6; }

@media (max-width: 620px) {
    .btn-run { margin-left: 0; width: 100%; }
    .fr-init { margin-left: 0; width: 100%; }
}
</style>
