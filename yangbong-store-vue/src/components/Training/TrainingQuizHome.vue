<template>
    <div id="training-quiz">
        <BrandHeader title="퀴즈" :back="TRAINING_PATH" />
        <main class="qz-main">
            <section class="score" aria-label="퀴즈 기록">
                <span class="emo"><img src="/img/emoji/trophy.png" alt="" /></span>
                <span><small>지금까지 맞힌 문제</small><b>{{ quiz.rightCount }} <i>/ {{ quiz.total }}</i></b></span>
            </section>

            <div class="actions">
                <button type="button" @click="router.push(quizSetPath('all'))"><img src="/img/emoji/target.png" alt="" />전체 풀기</button>
                <button type="button" :disabled="!quiz.wrongQuestions.length" @click="router.push(quizSetPath('wrong'))">
                    <img src="/img/emoji/repeat.png" alt="" />틀린 문제<em v-if="quiz.wrongQuestions.length">{{ quiz.wrongQuestions.length }}</em>
                </button>
            </div>

            <h2>수업별로 풀기</h2>
            <ul>
                <li v-for="c in sets" :key="c.slug">
                    <button type="button" class="set" @click="router.push(quizSetPath(c.slug))">
                        <b>{{ c.name }}</b>
                        <span :class="{ done: quiz.rightIn(c.questions) === c.questions.length }">{{ quiz.rightIn(c.questions) }}/{{ c.questions.length }}</span>
                        <i aria-hidden="true">›</i>
                    </button>
                </li>
            </ul>
        </main>
    </div>
</template>

<script setup>
/** 퀴즈 모음: 전체 풀기 · 틀린 문제 · 수업별 풀기 */
import { TRAINING_PATH } from '@scripts/training.js';
import { quizChapters, quizSetPath } from '@scripts/trainingQuiz.js';
import { useQuizStore } from '@scripts/stores/quiz-store.js';

const router = useRouter();
const quiz = useQuizStore();
const sets = quizChapters();
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#training-quiz { min-height: 100vh; background: $card; color: $ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; -webkit-font-smoothing: antialiased; }
button { border: 0; color: inherit; font: inherit; letter-spacing: inherit; cursor: pointer; -webkit-tap-highlight-color: transparent; }
.qz-main { max-width: 720px; margin: 0 auto; padding: 6px $pad-x 24px; box-sizing: border-box; }
.score {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 18px;
    border-radius: $radius;
    background: $honey-100;
    .emo { width: 60px; height: 60px; flex: none; display: flex; align-items: center; justify-content: center; border-radius: $radius; background: $card; }
    img { width: 42px; height: 42px; }
    small { font-size: 13px; color: $sub-ink; }
    b { display: block; margin-top: 2px; font-size: 24px; font-weight: 700; }
    i { font-size: 15px; font-style: normal; font-weight: 500; color: $sub; }
}
.actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    margin-top: 8px;
    button {
        height: 58px;
        padding: 0 12px;
        border-radius: $radius;
        background: $honey-strip;
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
        font-weight: 700;
        &:disabled { color: $sub-2; cursor: default; img { opacity: .45; } }
    }
    img { width: 26px; height: 26px; }
    em { margin-left: auto; color: $amber-700; font-style: normal; }
}
h2 { margin: 24px 0 6px; font-size: 14px; font-weight: 600; color: $sub; }
ul { margin: 0; padding: 0; list-style: none; }
.set {
    width: 100%;
    height: 58px;
    padding: 0;
    display: flex;
    align-items: center;
    border-bottom: 1px solid $line;
    background: transparent;
    text-align: left;
    b { flex: 1; min-width: 0; font-size: 16px; font-weight: 600; }
    span { font-size: 13px; color: $sub; &.done { color: $amber-700; font-weight: 600; } }
    i { margin-left: 8px; font-style: normal; color: $sub-2; }
}
</style>
