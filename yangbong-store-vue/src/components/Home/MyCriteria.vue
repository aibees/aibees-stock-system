<template>
    <!-- 홈 '내 기준' 카드(2026-11-22 회의 결정 4번). 상태 3분기:
         A 로그인 전 → 로그인하고 내 기준 만들기 / B 로그인·기준 없음 → 내 기준 만들기 / C 기준 있음 → 걸린 종목 + 조건 요약 + 백테스트 진입 -->
    <section class="sec criteria" aria-labelledby="criteria-title">
        <div class="sec-head">
            <h2 id="criteria-title">내 기준</h2>
            <button v-if="state === 'C'" type="button" class="meta-link" @click="router.push(PRESET_PATH)">기준 바꾸기</button>
        </div>

        <!-- A · B: 만들기 유도 -->
        <div v-if="state !== 'C'" class="c-empty">
            <p class="c-lead">{{ state === 'A' ? '내가 정한 기준으로 종목을 골라보세요.' : '아직 내 기준이 없어요.' }}</p>
            <p class="c-sub">거래량이 몇 배 늘었는지, 몇 일선 위인지처럼 고르는 조건을 직접 정해요.</p>
            <button type="button" class="c-cta" @click="onCreate">{{ state === 'A' ? '로그인하고 내 기준 만들기' : '내 기준 만들기' }}</button>
        </div>

        <!-- C: 기준 있음 -->
        <div v-else class="c-body">
            <p class="c-name">{{ typeName }}</p>
            <ul class="c-conds">
                <li v-for="c in condLines" :key="c">{{ c }}</li>
                <li v-if="!condLines.length">켜 둔 조건이 없어요</li>
            </ul>
            <p class="c-rule">{{ ruleText }}</p>

            <div class="c-hit" :class="{ none: !matchedCount }">
                <template v-if="matchedCount">
                    <span class="c-hit-tag">오늘 걸린 종목 {{ matchedCount }}개</span>
                    <span v-if="firstName" class="c-hit-name">{{ firstName }}<em v-if="matchedCount > 1"> 외 {{ matchedCount - 1 }}</em></span>
                </template>
                <span v-else class="c-hit-name">오늘은 이 기준에 걸린 종목이 없어요</span>
            </div>

            <button v-if="backtestOpen" type="button" class="c-cta" @click="router.push(BACKTEST_PATH)">이 기준, 과거에 넣어보기</button>
        </div>
    </section>
</template>

<script setup>
import { indicatorSummary, BASIC_INDICATORS, passRuleText } from '@scripts/indicators.js';

const props = defineProps({
    isLoggedIn: { type: Boolean, default: false },
    hasCriteria: { type: Boolean, default: false },
    type: { type: Object, required: true },          // persona.currentType: {name, settings}
    matchedCount: { type: Number, default: 0 },       // 오늘 내 기준에 걸린 종목 수
    firstName: { type: String, default: '' },         // 그 중 맨 앞 종목
    backtestOpen: { type: Boolean, default: false },  // 백테스트 메뉴가 열려 있을 때만 진입 버튼을 보인다
});

const router = useRouter();
const PRESET_PATH = '/stock/preset';
const BACKTEST_PATH = '/stock/backtest';

const state = computed(() => (!props.isLoggedIn ? 'A' : (props.hasCriteria ? 'C' : 'B')));
const typeName = computed(() => props.type?.name ?? '');
const condLines = computed(() => BASIC_INDICATORS
    .map(d => indicatorSummary(d.key, props.type.settings))
    .filter(Boolean));
const ruleText = computed(() => passRuleText(props.type.settings));

// 로그인 전이면 로그인 화면으로 보낸다(로그인하면 기준 만들기 화면으로 돌아온다 — 라우터 가드의 '로그인 후 복귀').
const onCreate = () => router.push(PRESET_PATH);
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

.sec { background: $card; padding: 28px $pad-x 24px; }
.sec-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
    h2 { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
}
.meta-link {
    min-height: 32px;
    padding: 0;
    border: 0;
    background: transparent;
    color: $sub;
    font: inherit;
    font-size: 13px;
    cursor: pointer;
    &::after { content: ' ›'; color: $sub-2; }
}

.c-empty, .c-body { margin-top: 12px; }
.c-lead { margin: 0; font-size: 16px; font-weight: 600; }
.c-sub { margin: 6px 0 0; font-size: 13px; line-height: 1.5; color: $sub; }

.c-name { margin: 0; font-size: 13px; color: $sub; }
.c-conds {
    margin: 8px 0 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 6px;
    li {
        position: relative;
        padding-left: 14px;
        font-size: 15px;
        &::before { content: ''; position: absolute; left: 0; top: 9px; width: 5px; height: 5px; border-radius: 3px; background: $honey-500; }
    }
}
.c-rule { margin: 10px 0 0; font-size: 12px; color: $sub-2; }

.c-hit {
    margin-top: 16px;
    padding: 12px 14px;
    border-radius: $radius;
    background: $honey-strip;
    display: flex;
    flex-direction: column;
    gap: 4px;
    &.none { background: $bg; }
}
.c-hit-tag { font-size: 12px; font-weight: 700; color: $amber-700; }
.c-hit-name { font-size: 16px; font-weight: 600; em { font-style: normal; font-weight: 400; color: $sub; } }

.c-cta {
    width: 100%;
    min-height: 48px;
    margin-top: 16px;
    border: 0;
    border-radius: $radius;
    background: $honey-300;
    color: $honey-ink;
    font: inherit;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
}
</style>
