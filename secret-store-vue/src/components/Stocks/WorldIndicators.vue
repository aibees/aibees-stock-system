<template>
    <div id="world-indicators">
        <Headers :prop_title="title" />

        <div class="contents">
            <section class="head-desc">
                <div class="head-left">
                    <h2 style="text-align: left;">국채금리 · 유가</h2>
                </div>

                <div class="head-actions">
                    <button class="btn-world-refresh" :disabled="isWorldLoading" @click="getWorldIndicators">
                        {{ isWorldLoading ? '불러오는 중…' : '새로고침' }}
                    </button>
                </div>
            </section>

            <nav v-if="!isWorldLoading && worldGroups.length > 0" class="indicator-shortcuts">
                <a v-for="group in worldGroups" :key="group.category" :href="`#indicator-${group.category}`"
                    class="shortcut-chip">{{ group.category_label }}</a>
            </nav>

            <section class="world-indicator">
                <template v-if="!isWorldLoading && worldGroups.length > 0">
                    <div v-for="group in worldGroups" :key="group.category" :id="`indicator-${group.category}`"
                        class="indicator-group">
                        <h3 class="indicator-group-title">{{ group.category_label }}</h3>
                        <div class="indicator-grid">
                            <div v-for="item in group.items" :key="item.series_id" class="indicator-card">
                                <div class="indicator-head">
                                    <h4>{{ item.label }}</h4>
                                    <div class="indicator-value" :class="rateClass(item.change)">
                                        {{ formatIndicatorValue(item.latest_value, group.unit) }}
                                        <span v-if="item.change != null" class="indicator-change">
                                            {{ formatIndicatorChange(item.change, group.unit) }}
                                        </span>
                                    </div>
                                </div>
                                <div class="indicator-chart">
                                    <IndicatorMiniChart :points="item.observations" />
                                </div>
                                <p class="indicator-summary">
                                    {{ item.label }} {{ group.metric_word }} {{ formatIndicatorValue(item.latest_value, group.unit) }}
                                    ({{ item.latest_date ?? '-' }})
                                    <template v-if="item.change != null">
                                        · 전일대비
                                        <span class="summary-change" :class="rateClass(item.change)">{{ formatIndicatorChange(item.change, group.unit) }}</span>
                                    </template>
                                    · 최근 {{ item.observations.length }}일 범위 {{ formatIndicatorRange(item.observations, group.unit) }}
                                </p>
                            </div>
                        </div>
                    </div>
                </template>

                <div v-else-if="isWorldLoading" class="loader-grid">
                    <div class="skeleton-card" v-for="n in 4" :key="n"></div>
                </div>

                <div v-else class="empty-box">
                    <p>지표 데이터를 가져오지 못했습니다.</p>
                </div>
            </section>
        </div>
    </div>
</template>

<script setup>
import IndicatorMiniChart from '../common/comp/IndicatorMiniChart.vue';
import aibeesApi from '@scripts/aibeesApi.js';

const title = ref('국채금리 · 유가');

/* ── 국채 금리 · 국제 유가 (FRED) ── */
const worldGroups = ref([]);
const isWorldLoading = ref(false);

const getWorldIndicators = async () => {
    isWorldLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/indicators/world');
        worldGroups.value = data.data ?? [];
    } catch (e) {
        console.error(e);
        worldGroups.value = [];
    } finally {
        isWorldLoading.value = false;
    }
};

onMounted(() => {
    getWorldIndicators();
});

const formatIndicatorValue = (value, unit) => {
    if (value == null) return '-';
    return unit === 'usd' ? `$${value.toFixed(2)}` : `${value.toFixed(2)}%`;
};
const formatIndicatorChange = (change, unit) => {
    if (change == null) return '';
    const sign = change >= 0 ? '+' : '';
    return unit === 'usd' ? `${sign}${change.toFixed(2)}달러` : `${sign}${change}%p`;
};
const formatIndicatorRange = (observations, unit) => {
    if (!observations || observations.length === 0) return '-';
    const values = observations.map(o => o.value);
    return `${formatIndicatorValue(Math.min(...values), unit)}~${formatIndicatorValue(Math.max(...values), unit)}`;
};

const rateClass = (rate) => {
    if (!rate) return '';
    const v = parseFloat(rate);
    if (v > 0) return 'rate-up';
    if (v < 0) return 'rate-down';
    return '';
};
</script>

<style scoped lang="scss">
@use '@@/common.scss' as *;


#world-indicators {
    min-height: 100vh;
    background: var(--sc-bg);
    color: var(--sc-text);
    font-family: 'Pretendard', -apple-system, sans-serif;
}

:global(html) {
    scroll-behavior: smooth;
}

.contents {
    max-width: 1040px;
    margin: 0 auto;
    padding: 28px 16px 100px;
}

/* ── Header ── */
.head-desc {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 24px;
    text-align: start;

    h2 {
        font-size: 1.4rem;
        font-weight: 700;
        margin: 0;
        color: var(--sc-text);
    }

    @media (max-width: 600px) {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
    }
}

.head-actions {
    display: flex;
    align-items: center;
    gap: 10px;

    @media (max-width: 600px) {
        width: 100%;
    }
}

.btn-world-refresh {
    padding: 8px 16px;
    border: 1px solid var(--sc-border);
    background: var(--sc-surface);
    color: var(--sc-text);
    font-size: 0.86rem;
    font-weight: 700;
    cursor: pointer;
    font-family: inherit;
    white-space: nowrap;
    transition: border-color .15s, color .15s;

    &:hover { border-color: var(--sc-text); color: var(--sc-text); }
    &:disabled { color: var(--sc-text-mute); cursor: not-allowed; }
}

.indicator-shortcuts {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 20px;
}

.shortcut-chip {
    padding: 6px 14px;
    border: 1px solid var(--sc-border);
    background: var(--sc-surface);
    color: var(--sc-text);
    font-size: 0.8rem;
    font-weight: 600;
    text-decoration: none;
    white-space: nowrap;
    transition: border-color .15s, color .15s;

    &:hover { border-color: var(--sc-text); color: var(--sc-text); }
}

.indicator-group {
    margin-bottom: 28px;

    &:last-child { margin-bottom: 0; }
}

.indicator-group-title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--sc-text);
    margin: 0 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--sc-border);
}

.indicator-grid {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.indicator-card {
    background: var(--sc-surface);
    border: 1px solid var(--sc-border);
    padding: 14px;
    transition: border-color .15s;

    &:hover { border-color: var(--sc-text); }
}

.indicator-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 8px;

    h4 {
        font-size: 0.9rem;
        font-weight: 700;
        margin: 0;
        color: var(--sc-text);
    }
}

.indicator-value {
    font-size: 1.05rem;
    font-weight: 800;
    color: var(--sc-text);
    white-space: nowrap;

    &.rate-up { color: var(--sc-text); }
    &.rate-down { color: var(--sc-text); }
}

.indicator-change {
    margin-left: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--sc-text-sub);
}

.indicator-chart {
    height: 90px;
    margin-bottom: 8px;
}

.indicator-summary {
    margin: 0;
    font-size: 0.76rem;
    color: var(--sc-text-sub);
    line-height: 1.4;
    text-align: left;

    .summary-change {
        font-weight: 700;

        &.rate-up { color: var(--sc-up); }
        &.rate-down { color: var(--sc-down); }
    }
}

/* ── Skeleton ── */
.loader-grid {
    display: grid;
    gap: 16px;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
}

.skeleton-card {
    height: 310px;
    background: var(--sc-surface-2);
    animation: pulse 1.6s infinite ease-in-out;
}

/* ── Empty ── */
.empty-box {
    text-align: center;
    padding: 80px 0;
    color: var(--sc-text-sub);
    font-size: 0.9rem;
}

@keyframes pulse {
    0%, 100% { opacity: .5; }
    50%       { opacity: .9; }
}
</style>
