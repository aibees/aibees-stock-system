<template>
    <div class="ht">
        <!-- 이어서 하기: 트레이닝 메뉴에서 옮겨 온 큰 카드(2026-11-24). 브랜드 갈색 면 + 꿀색 버튼(보색 파랑은 어색해서 갈색으로) -->
        <section class="ht-sec resume-sec" aria-label="이어서 하기">
            <button type="button" class="resume" :class="{ finished: !next }" @click="goResume">
                <span class="r-tag">{{ tag }}</span>
                <b class="r-title">{{ title }}</b>
                <span v-if="meta" class="r-meta">{{ meta }}</span>
                <span v-if="sub" class="r-sub">{{ sub }}</span>
                <span class="r-bar" role="progressbar" aria-label="완료한 단계"
                    :aria-valuenow="store.doneCount" aria-valuemin="0" :aria-valuemax="store.total">
                    <span :style="{ width: `${pct}%` }"></span>
                </span>
                <span class="r-foot">
                    <span class="r-count"><b>{{ store.doneCount }}</b> / {{ store.total }} 단계</span>
                    <i class="r-go">{{ cta }}<em aria-hidden="true">›</em></i>
                </span>
            </button>
        </section>

        <!-- 이번 주 학습: 일~토. 수업 단계 · 퀴즈 · 차트 퀴즈 중 하나라도 한 날이 채워진다(이 기기에만 기록 — studyLog.js) -->
        <section class="ht-sec week" aria-labelledby="week-title">
            <div class="ht-head">
                <h2 id="week-title">이번 주 학습</h2>
                <span class="ht-meta">{{ doneCount }}일 / 7일</span>
            </div>
            <ol class="days">
                <li v-for="d in week" :key="d.key" class="day" :class="d.state"
                    :aria-label="`${d.label}요일 ${d.date}일, ${stateText(d)}`">
                    <span class="d-label" aria-hidden="true">{{ d.label }}</span>
                    <span class="d-dot" aria-hidden="true">
                        <svg v-if="d.done" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"></path></svg>
                        <template v-else>{{ d.date }}</template>
                    </span>
                </li>
            </ol>
            <p class="week-note">{{ weekNote }}</p>
        </section>
    </div>
</template>

<script setup>
/**
 * 홈 > 트레이닝 탭. 이어서 하기(큰 카드) + 이번 주(일~토) 학습 여부.
 * 이어서 하기는 원래 트레이닝 첫 화면에 있던 카드를 옮긴 것이다(2026-11-24).
 */
import { findChapter, stageNoText, stagePath } from '@scripts/training.js';
import { QUIZ_PATH } from '@scripts/trainingQuiz.js';
import { useTrainingStore } from '@scripts/stores/training-store.js';
import { useStudyWeek } from '@scripts/studyLog.js';

const router = useRouter();
const store = useTrainingStore();
const { week, doneCount } = useStudyWeek();

const next = computed(() => store.nextStage);
const pct = computed(() => (store.total ? Math.round(store.doneCount / store.total * 100) : 0));
const started = computed(() => store.doneCount > 0);

const tag = computed(() => (!next.value ? '수업 완료' : started.value ? '이어서 하기' : '처음 시작하기'));
const title = computed(() => (next.value ? (next.value.short || next.value.title) : '모든 수업을 마쳤어요'));
const meta = computed(() => {
    const n = next.value;
    if (!n) return '';
    // 예) 내 돈 관리 기초 · 3강 / 차트 보는 법 · 기초 · 2단계 (번호는 코스 안 순번 — scripts/training.js stageNoText)
    const ch = findChapter(n.chapterSlug);
    return `${ch?.name ?? ''} · ${stageNoText(n)}`.replace(/^ · /, '');
});
const sub = computed(() => (next.value ? (next.value.sub || '') : '퀴즈로 한 번 더 짚어 보세요'));
const cta = computed(() => (!next.value ? '퀴즈 풀기' : started.value ? '계속하기' : '시작하기'));

const goResume = () => router.push(next.value ? stagePath(next.value) : QUIZ_PATH);

const stateText = (d) => ({ done: '학습함', today: '오늘', missed: '쉬었어요', future: '아직 안 왔어요' })[d.state];
const todayStudied = computed(() => week.value.some(d => d.isToday && d.done));
const weekNote = computed(() => {
    if (todayStudied.value) return '오늘 학습을 마쳤어요. 내일도 한 단계만 해 보세요.';
    return doneCount.value
        ? `이번 주 ${doneCount.value}일 학습했어요. 오늘은 한 단계만 해 볼까요?`
        : '수업 한 단계, 퀴즈 한 문제만 풀어도 그날이 채워져요.';
});
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

button { font: inherit; letter-spacing: inherit; }

.ht { display: flex; flex-direction: column; gap: $band-h; }
.ht-sec { background: $card; padding: $sec-pt $pad-x $sec-pb; }
.ht-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: $head-gap;
    h2 { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
}
.ht-meta { font-size: 13px; color: $sub; white-space: nowrap; }

/* ── 이어서 하기: 큰 카드. 브랜드 갈색 면 + 흰 글자 + 꿀색 버튼 ── */
.resume-sec { padding-top: 16px; }
.resume {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    width: 100%;
    min-height: 220px;
    box-sizing: border-box;
    padding: 22px 20px 18px;
    border: 0;
    border-radius: 18px;
    background: linear-gradient(145deg, #7A4623 0%, #9A6034 100%);   // 브랜드 갈색(#895129, favicon·__variables.scss $yb-brown) 계열
    color: #fff;
    text-align: left;
    cursor: pointer;
    overflow: hidden;
    -webkit-tap-highlight-color: transparent;
    box-shadow: 0 8px 20px rgba(137, 81, 41, .25);
    &::after {   // 모서리 장식 — 꿀방울 느낌의 옅은 원
        content: '';
        position: absolute;
        right: -36px;
        top: -36px;
        width: 140px;
        height: 140px;
        border-radius: 50%;
        background: rgba(255, 255, 255, .09);
        pointer-events: none;
    }
    &.finished { background: linear-gradient(145deg, #5B3A1E 0%, #7C5230 100%); box-shadow: 0 8px 20px rgba(91, 58, 30, .25); }
}
.r-tag {
    align-self: flex-start;
    height: 26px;
    padding: 0 11px;
    border-radius: 13px;
    background: rgba(255, 255, 255, .2);
    font-size: 13px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
}
.r-title { display: block; margin-top: 16px; font-size: 26px; font-weight: 800; line-height: 1.25; letter-spacing: -0.8px; word-break: keep-all; }
.r-meta { margin-top: 8px; font-size: 14px; font-weight: 600; color: rgba(255, 255, 255, .85); }
.r-sub { margin-top: 3px; font-size: 14px; color: rgba(255, 255, 255, .72); word-break: keep-all; }
.r-bar {
    display: block;
    height: 8px;
    margin-top: auto;
    border-radius: 4px;
    background: rgba(255, 255, 255, .25);
    overflow: hidden;
    span { display: block; height: 100%; border-radius: 4px; background: $honey-300; }
}
.r-foot { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 12px; }
.r-count { font-size: 13px; color: rgba(255, 255, 255, .85); b { font-size: 15px; color: #fff; } }
.r-go {
    height: 42px;
    padding: 0 18px;
    border-radius: 21px;
    background: $honey-300;
    color: $honey-ink;
    font-size: 15px;
    font-style: normal;
    font-weight: 800;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    em { font-style: normal; font-size: 18px; line-height: 1; }
}
.resume:active .r-go { background: $honey-500; }

/* ── 이번 주 학습(일~토) ── */
.days { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; margin: 4px 0 0; padding: 0; list-style: none; }
.day { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.d-label { font-size: 13px; font-weight: 600; color: $sub; }
.d-dot {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 600;
    color: $sub-2;
    background: $band;
    svg { width: 20px; height: 20px; }
}
.day.done .d-dot { background: $honey-300; color: $honey-ink; }
.day.done .d-label { color: $amber-700; }
.day.today .d-dot { background: $card; color: $amber-700; box-shadow: inset 0 0 0 2px $honey-500; font-weight: 800; }
.day.today .d-label { color: $amber-700; font-weight: 800; }
.day.missed .d-dot { color: $sub; }
.day.future .d-dot { background: transparent; box-shadow: inset 0 0 0 1px $line; }
.week-note { margin: 16px 0 0; font-size: 13.5px; line-height: 1.5; color: $sub-ink; word-break: keep-all; }
</style>
