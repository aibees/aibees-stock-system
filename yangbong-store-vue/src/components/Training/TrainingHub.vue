<template>
    <div id="training-hub">
        <header class="hub-head">
            <div>
                <h1>트레이닝</h1>
                <p>오늘은 무엇부터 해볼까요?</p>
            </div>
            <img src="/img/emoji/bee.png" alt="" width="44" height="44" />
        </header>

        <main class="hub-main">
            <!-- 용어 검색(2026-11-24): 누르면 용어 사전 검색으로 -->
            <form class="search" role="search" @submit.prevent="searchTerm">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
                <label class="sr-only" for="hub-q">용어 검색</label>
                <input id="hub-q" v-model="q" type="search" placeholder="용어 검색 (DSR, ISA, 점도표…)" autocomplete="off" enterkeyhint="search" />
            </form>
            <!-- 오늘의 한 문제: 맨 위 카드(2026-11-23, 맨 아래 줄에서 옮김) -->
            <button v-if="today" type="button" class="today" @click="router.push(quizSetPath('today'))">
                <span class="today-text">
                    <small>오늘의 한 문제</small>
                    <span>{{ today.q }}</span>
                </span>
                <i>풀기</i>
            </button>

            <!-- '이어서 하기'는 2026-11-24 홈(트레이닝 탭)으로 옮겼다 -->

            <!-- 다시 보기(2026-11-24): 복습하기 + 오답노트 · 헷갈린 용어 -->
            <h2>다시 보기</h2>
            <button type="button" class="review" @click="router.push(REVIEW_PATH)">
                <span class="emo"><img src="/img/emoji/repeat.png" alt="" /></span>
                <span class="resume-text">
                    <b>복습하기</b>
                    <small v-if="review.dueList.length">오늘 다시 볼 때가 된 것 <em>{{ review.dueList.length }}개</em></small>
                    <small v-else-if="review.wrongList.length || review.termList.length">오늘 볼 것은 다 했어요</small>
                    <small v-else>틀린 문제와 헷갈린 용어가 여기 모여요</small>
                </span>
                <i v-if="review.dueList.length">시작</i>
            </button>
            <div class="minis">
                <button type="button" class="mini" @click="router.push(`${REVIEW_PATH}?tab=wrong`)">
                    <span class="ic wrong" aria-hidden="true">✕</span><b>오답노트</b><em>{{ review.wrongList.length }}</em>
                </button>
                <button type="button" class="mini" @click="router.push(`${REVIEW_PATH}?tab=term`)">
                    <span class="ic conf" aria-hidden="true">?</span><b>헷갈린 용어</b><em>{{ review.termList.length }}</em>
                </button>
            </div>

            <h2>기본기 트레이닝</h2>
            <!-- 재테크 학습하기(2026-11-24): 경제 기초(무료)와 투자 실전 두 카드를 한 카드로 합쳤다. 두 코스는 열리는 화면 위쪽 탭으로 고른다 -->
            <button type="button" class="lesson-card" @click="router.push(LESSONS_PATH)">
                <span class="emo"><img src="/img/emoji/books.png" alt="" /></span>
                <span class="lesson-text">
                    <b>재테크 학습하기</b>
                    <small>{{ learnSub }}</small>
                    <span class="bar" role="progressbar" aria-label="완료한 단계" :aria-valuenow="store.doneCount" aria-valuemin="0" :aria-valuemax="store.total">
                        <span :style="{ width: `${pct}%` }"></span>
                    </span>
                </span>
            </button>

            <div class="tiles">
                <button type="button" class="tile" @click="router.push(QUIZ_PATH)">
                    <span class="emo"><img src="/img/emoji/target.png" alt="" /></span>
                    <b>퀴즈</b>
                    <small>{{ quiz.total }}문제 풀어보기</small>
                </button>
                <button type="button" class="tile" @click="router.push(GLOSSARY_PATH)">
                    <span class="emo"><img src="/img/emoji/open-book.png" alt="" /></span>
                    <b>용어 사전</b>
                    <small>{{ termCount }}개 찾아보기</small>
                </button>
            </div>

            <!-- 차트 트레이닝: 기본기 트레이닝 아래(2026-11-24) -->
            <h2>차트 트레이닝</h2>
            <button type="button" class="lesson-card" @click="router.push(CHART_QUIZ_PATH)">
                <span class="emo"><img src="/img/emoji/chart.png" alt="" /></span>
                <span class="lesson-text">
                    <b>차트 퀴즈</b>
                    <small>실제 과거 차트를 보고 20일 뒤를 예상해 보세요 · 하루 3문제</small>
                </span>
            </button>
            <button type="button" class="review-link" @click="router.push(CHART_QUIZ_REVIEW_PATH)">다른 방향이었던 문제 다시 보기<i aria-hidden="true">›</i></button>

            <!-- 화면 안 광고 1칸(앱 전용, 하단 탭 화면마다 하나 — AdInlineSlot). 트레이닝 헤더는 고정이 아니라 자를 헤더가 없다 -->
            <AdInlineSlot />

            <p class="note">설명용 자료이며 특정 종목의 매수·매도를 권하지 않습니다. 투자 판단과 책임은 본인에게 있습니다.</p>
        </main>
    </div>
</template>

<script setup>
/** 트레이닝 첫 화면: 용어 검색 · 오늘의 한 문제 · 다시 보기 · 기본기 트레이닝(재테크 학습하기 · 퀴즈 · 용어 사전) · 차트 트레이닝. 이어서 하기는 홈의 트레이닝 탭에 있다. */
import AdInlineSlot from '../common/AdInlineSlot.vue';
import { courses, LESSONS_PATH, GLOSSARY_PATH } from '@scripts/training.js';
import { glossaryTerms } from '@scripts/glossary.js';
import { QUIZ_PATH, quizSetPath, todayQuestion } from '@scripts/trainingQuiz.js';
import { CHART_QUIZ_PATH, CHART_QUIZ_REVIEW_PATH } from '@scripts/trainingChart.js';
import { useTrainingStore } from '@scripts/stores/training-store.js';
import { useQuizStore } from '@scripts/stores/quiz-store.js';
import { useReviewStore, REVIEW_PATH } from '@scripts/stores/review-store.js';

const router = useRouter();
const store = useTrainingStore();
const quiz = useQuizStore();

const review = useReviewStore();
// 재테크 학습하기 카드: 두 코스(경제 기초 · 투자 실전)를 합쳐서 한 줄로 요약
const courseList = courses();
const learnSub = computed(() => {
    const size = courseList.map(c => `${c.name}${c.free ? '(무료)' : ''} ${c.stages.length}${c.unit}`).join(' · ');
    return store.doneCount ? `${size} · ${store.doneCount}/${store.total} 들음` : size;
});
const q = ref('');
const searchTerm = () => router.push({ path: GLOSSARY_PATH, query: q.value.trim() ? { q: q.value.trim() } : {} });
const termCount = glossaryTerms().length;
const today = todayQuestion();
const pct = computed(() => (store.total ? Math.round(store.doneCount / store.total * 100) : 0));
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#training-hub {
    min-height: 100vh;
    background: $card;
    color: $ink;
    text-align: left;
    font-family: $font-body;
    letter-spacing: -0.2px;
    -webkit-font-smoothing: antialiased;
}
button { width: 100%; border: 0; color: inherit; font: inherit; letter-spacing: inherit; text-align: left; cursor: pointer; -webkit-tap-highlight-color: transparent; }
.hub-head, .hub-main { max-width: 720px; margin: 0 auto; box-sizing: border-box; }
.hub-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px $pad-x 14px;
    h1 { margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.6px; }
    p { margin: 5px 0 0; font-size: 14px; color: $sub; }
    img { display: block; }
}
.hub-main { padding: 0 $pad-x 24px; }
.emo { flex: none; display: flex; align-items: center; justify-content: center; border-radius: $radius; background: $card; img { display: block; } }

h2 { margin: 24px 0 10px; font-size: 18px; font-weight: 700; letter-spacing: -0.4px; }

.lesson-card {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 18px;
    border-radius: $radius;
    background: $honey-100;
    .emo { width: 68px; height: 68px; img { width: 48px; height: 48px; } }
    b { display: block; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
    small { display: block; margin-top: 4px; font-size: 13px; color: $sub-ink; }
}
.lesson-text { flex: 1; min-width: 0; }
.review-link {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 44px;
    margin-top: 2px;
    padding: 0 4px;
    background: transparent;
    font-size: 14px;
    font-weight: 600;
    color: $sub-ink;
    i { font-style: normal; color: $sub-2; }
}
.bar { display: block; height: 6px; margin-top: 10px; border-radius: 3px; background: $card; overflow: hidden; span { display: block; height: 100%; border-radius: 3px; background: $honey-500; } }

.tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 8px; }
.tile {
    min-height: 132px;
    padding: 16px;
    border-radius: $radius;
    background: $honey-strip;
    .emo { width: 48px; height: 48px; img { width: 34px; height: 34px; } }
    b { display: block; margin-top: 14px; font-size: 17px; font-weight: 700; }
    small { display: block; margin-top: 3px; font-size: 13px; color: $sub-ink; }
}
/* 오늘의 한 문제 카드(맨 위). 이어서 하기 카드와 같은 모양 — 2026-11-23 */
.today {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    border-radius: $radius;
    background: $honey-100;
    small { display: block; font-size: 12px; font-weight: 600; color: $amber-700; }
    .today-text > span { display: block; margin-top: 5px; font-size: 15px; font-weight: 600; line-height: 1.45; word-break: keep-all; }
    i { flex: none; margin-left: auto; height: 34px; padding: 0 12px; border-radius: 8px; background: $honey-300; color: $honey-ink; font-size: 13px; font-style: normal; font-weight: 700; display: flex; align-items: center; }
}
.today-text { flex: 1; min-width: 0; }
.note { margin: 12px 0 0; font-size: 12px; line-height: 1.6; color: $sub-2; word-break: keep-all; }

/* ══ 2026-11-22 간격 통일(8px 격자, 토큰: _home-tokens.scss — 홈과 같은 규칙) — 위의 값보다 이 블록이 우선 ══
   섹션 위 24 · 제목→내용 12 · 카드 안쪽 16 · 카드·요소 사이 12 · 한 줄 56 */
.hub-head { padding: $card-pad $pad-x $gap; }
.hub-main { padding-bottom: $sec-pb; }
.resume { padding: $card-pad; gap: $gap; }
h2 { margin: $sec-pt 0 $head-gap; }
.lesson-card { padding: $card-pad; gap: $gap; }
.review-link { margin-top: 0; }
.tiles { gap: $gap; margin-top: $gap; }
.tile { padding: $card-pad; b { margin-top: $gap; } }
.today { padding: $card-pad; gap: $gap; }
.today + .resume { margin-top: $gap; }
.note { margin-top: $gap; }

/* ══ 2026-11-24 용어 검색 · 다시 보기 · 코스 카드 ══ */
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.search { display: flex; align-items: center; gap: 8px; height: 44px; margin-bottom: $gap; padding: 0 $card-pad; border-radius: $radius; background: $band; color: $sub;
    input { flex: 1; min-width: 0; height: 100%; border: 0; background: transparent; color: $ink; font: inherit; font-size: 16px; outline: none;
        &::placeholder { color: $sub; } &::-webkit-search-cancel-button { -webkit-appearance: none; } } }
.review { display: flex; align-items: center; gap: $gap; padding: $card-pad; border-radius: $radius; background: $honey-strip;
    .emo { width: 44px; height: 44px; img { width: 30px; height: 30px; } }
    b { display: block; font-size: 16px; font-weight: 700; }
    small { display: block; margin-top: 2px; font-size: 13px; color: $sub-ink; em { font-style: normal; font-weight: 700; color: $amber-700; } }
    i { margin-left: auto; height: 34px; padding: 0 12px; border-radius: 8px; background: $honey-300; color: $honey-ink; font-size: 13px; font-style: normal; font-weight: 700; display: flex; align-items: center; } }
.minis { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: $gap; margin-top: $gap; }
.mini { display: flex; align-items: center; gap: 10px; min-height: 52px; padding: 0 14px; border: 1px solid $line; border-radius: $radius; background: $card;
    b { font-size: 14.5px; font-weight: 600; white-space: nowrap; } em { margin-left: auto; font-style: normal; font-size: 15px; font-weight: 700; color: $ink; } }
.ic { flex: none; width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 800;
    &.wrong { background: $up-bg; color: $up; } &.conf { background: $honey-100; color: $amber-700; } }
.course + .course { margin-top: $gap; }
.course.invest { background: $honey-50; box-shadow: inset 0 0 0 1px #FFEBC2; }
.course-k { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; color: $amber-700; }
.free { padding: 1px 6px; border-radius: 6px; background: $card; box-shadow: inset 0 0 0 1px #FFE0A3; font-size: 11px; }
.course b { margin-top: 2px; }
</style>
