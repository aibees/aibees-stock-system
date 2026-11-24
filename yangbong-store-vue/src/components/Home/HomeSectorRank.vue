<template>
    <section v-if="show" class="sr" aria-labelledby="sr-title">
        <div class="sr-head">
            <h2 id="sr-title">오늘의 업종 순위</h2>
            <span v-if="basisText" class="sr-meta">{{ basisText }}</span>
        </div>

        <div class="sr-seg" role="tablist" aria-label="시장">
            <button v-for="m in MARKETS" :key="m.key" type="button" role="tab" :class="{ on: m.key === market }"
                :aria-selected="m.key === market ? 'true' : 'false'" @click="market = m.key">{{ m.label }}</button>
        </div>

        <div v-if="isLoading" class="sr-skel" aria-busy="true" aria-label="불러오는 중"><i v-for="n in TOP_COUNT" :key="n"></i></div>
        <ol v-else-if="rows.length" class="sr-list">
            <li v-for="(r, i) in rows" :key="r.sector_cd" class="sr-row">
                <span class="sr-rank">{{ i + 1 }}</span>
                <span class="sr-name">{{ r.sector_name }}</span>
                <span class="sr-bar" aria-hidden="true"><span :class="r.cls" :style="{ width: r.barPct + '%' }"></span></span>
                <b class="sr-rate badge" :class="r.cls">{{ r.rateText }}</b>
            </li>
        </ol>
        <p v-else class="sr-empty">업종 데이터가 없어요.</p>

        <p v-if="rows.length" class="sr-note">업종에 속한 회사 주가를 시가총액으로 묶어 계산해요.</p>
    </section>
</template>

<script setup>
/**
 * 홈 > 시장 탭: 오늘의 업종 순위(2026-11-24 신규).
 *   GET /api/v1/stocks/sectors — 업종 화면(StockSector)과 같은 응답(시장별 업종 요약, 등락률 = 시가총액 가중, 비로그인 허용).
 *   코스피·코스닥을 나눠 등락률 높은 순 TOP 5. '미분류'(0000)와 값 없는 업종은 뺀다.
 *   데이터를 못 받으면 카드를 통째로 숨긴다(홈이 비어 보이지 않게).
 */
import aibeesApi from '@scripts/aibeesApi.js';
import { numOrNull } from '@scripts/stockSignals.js';
import { shortYmd } from '@scripts/marketFormat.js';

const MARKETS = [{ key: 'KOSPI', label: '코스피' }, { key: 'KOSDAQ', label: '코스닥' }];
const TOP_COUNT = 5;
const UNCLASSIFIED_CD = '0000';

const market = ref('KOSPI');
const sectors = ref([]);
const ymd = ref(null);
const isLoading = ref(true);
const failed = ref(false);

const signed = (n) => `${n > 0 ? '+' : (n < 0 ? '−' : '')}${Math.abs(n).toFixed(2)}%`;

const rows = computed(() => {
    const top = sectors.value
        .filter(s => s.market === market.value && s.sector_cd !== UNCLASSIFIED_CD && numOrNull(s.chg_rate) !== null)
        .sort((a, b) => numOrNull(b.chg_rate) - numOrNull(a.chg_rate))
        .slice(0, TOP_COUNT);
    // 막대 길이는 이 5개 중 가장 큰 절댓값을 100% 로
    const max = Math.max(...top.map(s => Math.abs(numOrNull(s.chg_rate))), 0.01);
    return top.map((s) => {
        const v = numOrNull(s.chg_rate);
        return {
            sector_cd: s.sector_cd, sector_name: s.sector_name,
            rateText: signed(v), cls: v > 0 ? 'up' : v < 0 ? 'down' : 'flat',
            barPct: Math.max(4, Math.round(Math.abs(v) / max * 100)),
        };
    });
});
const basisText = computed(() => (ymd.value ? `${shortYmd(ymd.value)} 종가 기준` : ''));
const show = computed(() => isLoading.value || !failed.value);

onMounted(async () => {
    try {
        const { data } = await aibeesApi.get('/api/v1/stocks/sectors');
        sectors.value = data?.data?.sectors ?? [];
        ymd.value = data?.data?.ymd ?? null;
        failed.value = !sectors.value.length;
    } catch {
        failed.value = true;
    } finally {
        isLoading.value = false;
    }
});
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

button { font: inherit; letter-spacing: inherit; }

.sr { background: $card; padding: $sec-pt $pad-x $sec-pb; }
.sr-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: $head-gap;
    h2 { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
}
.sr-meta { font-size: 13px; color: $sub; white-space: nowrap; }

.sr-seg {
    display: flex;
    gap: 4px;
    padding: 3px;
    border-radius: $radius;
    background: $band;
    button {
        flex: 1;
        height: 34px;
        border: 0;
        border-radius: 9px;
        background: transparent;
        color: $sub;
        font-size: 14px;
        cursor: pointer;
        &.on { background: $card; color: $ink; font-weight: 700; box-shadow: 0 1px 2px rgba(0, 0, 0, .08); }
    }
}

.sr-list { margin: 8px 0 0; padding: 0; list-style: none; }
.sr-row { display: flex; align-items: center; gap: 12px; min-height: $row-h; }
.sr-rank { flex: none; width: 16px; font-size: 17px; font-weight: 700; color: $amber-700; }
.sr-name { flex: none; width: 96px; font-size: 16px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sr-bar {
    flex: 1;
    min-width: 0;
    height: 8px;
    border-radius: 4px;
    background: $band;
    overflow: hidden;
    span { display: block; height: 100%; border-radius: 4px; background: $sub-2; &.up { background: $up; } &.down { background: $down; } }
}
.badge {
    flex: none;
    min-width: 66px;
    height: 24px;
    padding: 0 6px;
    border-radius: $radius-sm;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 600;
    color: $sub;
    background: $band;
    &.up { color: $up; background: $up-bg; }
    &.down { color: $down; background: $down-bg; }
}
.sr-note { margin: 8px 0 0; font-size: 12px; color: $sub; }
.sr-empty { margin: 0; padding: 24px 0; text-align: center; font-size: 13px; color: $sub; }
.sr-skel { padding: 12px 0 0; i { display: block; height: 40px; margin-bottom: 8px; border-radius: 8px; background: $bg; animation: sr-pulse 1.6s infinite ease-in-out; } }
@keyframes sr-pulse { 50% { opacity: .55; } }
@media (prefers-reduced-motion: reduce) { .sr-skel i { animation: none; } }
</style>
