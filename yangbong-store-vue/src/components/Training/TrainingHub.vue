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
            <!-- 오늘의 한 문제: 맨 위 카드(2026-11-23, 맨 아래 줄에서 옮김) -->
            <button v-if="today" type="button" class="today" @click="router.push(quizSetPath('today'))">
                <span class="today-text">
                    <small>오늘의 한 문제</small>
                    <span>{{ today.q }}</span>
                </span>
                <i>풀기</i>
            </button>

            <button v-if="next" type="button" class="resume" @click="router.push(stagePath(next))">
                <span class="emo"><img src="/img/emoji/honey.png" alt="" /></span>
                <span class="resume-text">
                    <small>{{ store.doneCount ? '이어서 하기' : '처음 시작하기' }}</small>
                    <b>{{ next.short || next.title }}</b>
                </span>
                <i>{{ store.doneCount ? '계속' : '시작' }}</i>
            </button>

            <h2>차트 트레이닝</h2>
            <button type="button" class="lesson-card" @click="router.push(CHART_QUIZ_PATH)">
                <span class="emo"><img src="/img/emoji/chart.png" alt="" /></span>
                <span class="lesson-text">
                    <b>차트 퀴즈</b>
                    <small>실제 과거 차트를 보고 20일 뒤를 예상해 보세요 · 하루 3문제</small>
                </span>
            </button>
            <button type="button" class="review-link" @click="router.push(CHART_QUIZ_REVIEW_PATH)">다른 방향이었던 문제 다시 보기<i aria-hidden="true">›</i></button>

            <h2>기본기 트레이닝</h2>
            <button type="button" class="lesson-card" @click="router.push(LESSONS_PATH)">
                <span class="emo"><img src="/img/emoji/books.png" alt="" /></span>
                <span class="lesson-text">
                    <b>수업 듣기</b>
                    <small>{{ chapterCount }}개 장 · {{ store.total }}단계</small>
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

            <p class="note">설명용 자료이며 특정 종목의 매수·매도를 권하지 않습니다. 투자 판단과 책임은 본인에게 있습니다.</p>
        </main>
    </div>
</template>

<script setup>
/** 트레이닝 첫 화면: 오늘의 한 문제 + 이어서 하기 + 차트 트레이닝(차트 퀴즈) + 기본기 트레이닝(수업 듣기 · 퀴즈 · 용어 사전) */
import { chapters, stagePath, LESSONS_PATH, GLOSSARY_PATH } from '@scripts/training.js';
import { glossaryTerms } from '@scripts/glossary.js';
import { QUIZ_PATH, quizSetPath, todayQuestion } from '@scripts/trainingQuiz.js';
import { CHART_QUIZ_PATH, CHART_QUIZ_REVIEW_PATH } from '@scripts/trainingChart.js';
import { useTrainingStore } from '@scripts/stores/training-store.js';
import { useQuizStore } from '@scripts/stores/quiz-store.js';

const router = useRouter();
const store = useTrainingStore();
const quiz = useQuizStore();

const chapterCount = chapters().length;
const termCount = glossaryTerms().length;
const today = todayQuestion();
const next = computed(() => store.nextStage);
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

.resume {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px;
    border-radius: $radius;
    background: $honey-strip;
    .emo { width: 44px; height: 44px; img { width: 30px; height: 30px; } }
    small { display: block; font-size: 12px; font-weight: 600; color: $amber-700; }
    b { display: block; margin-top: 2px; font-size: 16px; font-weight: 600; }
    i { margin-left: auto; height: 34px; padding: 0 12px; border-radius: 8px; background: $honey-300; color: $honey-ink; font-size: 13px; font-style: normal; font-weight: 700; display: flex; align-items: center; }
}
.resume-text { min-width: 0; }
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
.today + .resume { margin-top: 12px; }
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
</style>
