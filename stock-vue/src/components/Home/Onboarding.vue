<template>
    <div id="onboarding">
        <!-- 상단: 이전 · 진행 바 · 건너뛰기(유형 바꾸기 화면에서는 닫기) -->
        <header class="ob-top">
            <button v-if="canBack" type="button" class="ob-icon" aria-label="이전" @click="back">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg>
            </button>
            <span v-else class="ob-icon-space" aria-hidden="true"></span>

            <div v-if="!pickOnly" class="ob-progress" role="progressbar" aria-label="질문 진행"
                :aria-valuemin="0" :aria-valuemax="questions.length" :aria-valuenow="answeredCount">
                <i :style="{ width: progressPct + '%' }"></i>
            </div>
            <span v-else class="ob-progress-space"></span>

            <button v-if="!pickOnly" type="button" class="ob-text-btn" @click="skip">건너뛰기</button>
            <button v-else type="button" class="ob-text-btn" @click="close">닫기</button>
        </header>

        <main class="ob-main">
            <!-- ── 질문: 한 화면에 하나. 고르면 바로 다음으로 ── -->
            <transition name="ob-fade" mode="out-in">
                <section v-if="phase === 'question'" :key="'q' + step" class="ob-question" aria-live="polite">
                    <p class="ob-count">{{ step + 1 }} / {{ questions.length }}</p>
                    <h1 class="ob-q">{{ question.text }}</h1>
                    <ul class="ob-options">
                        <li v-for="(o, i) in question.options" :key="i">
                            <button type="button" class="ob-option" :class="{ on: answers[step] === i }"
                                :aria-pressed="answers[step] === i ? 'true' : 'false'" @click="choose(i)">
                                <span class="ob-option-label">{{ o.label }}</span>
                                <span class="ob-check" aria-hidden="true">{{ answers[step] === i ? '✓' : '' }}</span>
                            </button>
                        </li>
                    </ul>
                </section>

                <!-- ── 결과: 유형 하나를 제안하고, 사용자가 직접 골라 확정한다(자동 적용하지 않는다) ── -->
                <section v-else key="result" class="ob-result">
                    <h1 class="ob-title">{{ pickOnly ? '내 성향 바꾸기' : '이렇게 시작해 보세요' }}</h1>
                    <p v-if="!pickOnly" class="ob-lead">
                        답하신 내용으로 보면 <b>{{ suggestedType.name }}</b>에 가깝습니다. 세 가지 중에서 직접 골라 주세요.
                    </p>
                    <p v-else class="ob-lead">고른 성향에 맞춰 종목의 순서와 정리할 가격이 바뀝니다.</p>

                    <ul class="ob-types" role="radiogroup" aria-label="성향">
                        <li v-for="t in types" :key="t.key">
                            <button type="button" role="radio" class="ob-type" :class="{ on: chosen === t.key }"
                                :aria-checked="chosen === t.key ? 'true' : 'false'" @click="chosen = t.key">
                                <span class="t-body">
                                    <span class="t-name-line">
                                        <span class="t-name">{{ t.name }}</span>
                                        <span v-if="!pickOnly && t.key === suggestion.type" class="t-mark">· 제안</span>
                                        <span v-if="pickOnly && t.key === persona.currentType.key" class="t-mark">· 지금 설정</span>
                                    </span>
                                    <span class="t-desc">{{ t.desc }}</span>
                                    <span class="t-stop">정리할 가격: 산 가격보다 {{ t.stopPct }}% 내려가면</span>
                                </span>
                                <span class="ob-check" aria-hidden="true">{{ chosen === t.key ? '✓' : '' }}</span>
                            </button>
                        </li>
                    </ul>

                    <!-- 화면 모드: 주식을 꾸준히 해 온 분(1번 질문)과 성향 바꾸기 화면에서만 묻는다 -->
                    <div v-if="showModeChoice" class="ob-mode">
                        <h2 class="ob-sub">화면</h2>
                        <ul class="ob-types" role="radiogroup" aria-label="화면 모드">
                            <li v-for="m in MODES" :key="m.key">
                                <button type="button" role="radio" class="ob-type compact" :class="{ on: modeChoice === m.key }"
                                    :aria-checked="modeChoice === m.key ? 'true' : 'false'" @click="modeChoice = m.key">
                                    <span class="t-body">
                                        <span class="t-name">{{ m.name }}</span>
                                        <span class="t-desc">{{ m.desc }}</span>
                                    </span>
                                    <span class="ob-check" aria-hidden="true">{{ modeChoice === m.key ? '✓' : '' }}</span>
                                </button>
                            </li>
                        </ul>
                    </div>

                    <p class="ob-note">시작 설정 제안이며 언제든 바꿀 수 있습니다.</p>
                </section>
            </transition>
        </main>

        <footer v-if="phase === 'result'" class="ob-foot">
            <button type="button" class="ob-cta" @click="confirm">{{ pickOnly ? '이 설정으로 바꾸기' : '이 설정으로 시작' }}</button>
        </footer>
    </div>
</template>

<script setup>
/**
 * 온보딩 — 성향 질문 5개 → 유형 제안 → 사용자가 골라 확정. 가입 없이 끝까지 진행된다.
 * 형태는 B안 고정(소개 슬라이드 없이 질문으로 바로 시작, 2026-11-15). 질문·유형은 persona 설정(데이터)에서 읽는다.
 *   /onboarding        : 질문부터(처음 실행 시 라우터가 한 번 보내고, 홈의 "처음이세요?"로 다시 연다)
 *   /onboarding?pick=1 : 질문 없이 유형 고르기만(홈의 "바꾸기")
 */
import { usePersonaStore } from '@scripts/stores/persona-store.js';
import { suggestFromAnswers, findType } from '@scripts/persona.js';

const router = useRouter();
const route = useRoute();
const persona = usePersonaStore();

const MODES = [
    { key: 'simple', name: '간편 모드', desc: '오늘 볼 것만 간단히 보여 드립니다.' },
    { key: 'expert', name: '전문가 모드', desc: '조건, 차트, 정렬까지 모두 보여 드립니다.' },
];

const pickOnly = computed(() => route.query.pick === '1');
const questions = computed(() => persona.config.questions);
const types = computed(() => persona.config.types);

const step = ref(0);
const answers = ref([]);
const phase = ref(pickOnly.value ? 'result' : 'question');
const question = computed(() => questions.value[step.value]);
const answeredCount = computed(() => answers.value.filter(a => a !== undefined && a !== null).length);
const progressPct = computed(() =>
    phase.value === 'result' ? 100 : Math.round(step.value / questions.value.length * 100));

const suggestion = computed(() => suggestFromAnswers(persona.config, answers.value));
const suggestedType = computed(() => findType(persona.config, suggestion.value.type));

const chosen = ref(pickOnly.value ? persona.currentType.key : null);
const modeChoice = ref(persona.effectiveMode);
const showModeChoice = computed(() => pickOnly.value || suggestion.value.mode === 'expert');

const canBack = computed(() => !pickOnly.value && (step.value > 0 || phase.value === 'result'));

let advanceTimer = null;
const choose = (i) => {
    const next = [...answers.value];
    next[step.value] = i;
    answers.value = next;
    // 고른 표시(✓)를 잠깐 보여 주고 넘어간다
    clearTimeout(advanceTimer);
    advanceTimer = setTimeout(() => {
        if (step.value < questions.value.length - 1) {
            step.value += 1;
        } else {
            chosen.value = suggestion.value.type;
            modeChoice.value = suggestion.value.mode;
            phase.value = 'result';
        }
    }, 180);
};

const back = () => {
    clearTimeout(advanceTimer);
    if (phase.value === 'result') {
        phase.value = 'question';
        step.value = questions.value.length - 1;
    } else if (step.value > 0) {
        step.value -= 1;
    }
};

const goHome = () => router.replace('/home');
const skip = () => { persona.skip(); goHome(); };
const close = () => goHome();
const confirm = () => {
    persona.decide(chosen.value ?? suggestion.value.type, showModeChoice.value ? modeChoice.value : null);
    goHome();
};

onMounted(() => persona.markSeen());
onBeforeUnmount(() => clearTimeout(advanceTimer));
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#onboarding {
    min-height: 100vh;
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    background: $card;
    color: $ink;
    text-align: left;
    font-family: $font-body;
}

/* ── 상단 ── */
.ob-top {
    position: sticky;
    top: env(safe-area-inset-top, 0px);
    z-index: 10;
    display: grid;
    grid-template-columns: 44px minmax(0, 1fr) auto;
    align-items: center;
    gap: 8px;
    max-width: 560px;
    width: 100%;
    margin: 0 auto;
    padding: 4px 8px;
    box-sizing: border-box;
    background: $card;
}
.ob-icon {
    width: 44px;
    height: 44px;
    border: 0;
    background: transparent;
    color: $brown-ink;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}
.ob-icon-space { width: 44px; height: 44px; }
.ob-progress {
    height: 4px;
    border-radius: 2px;
    background: $line-soft;
    overflow: hidden;
    i {
        display: block;
        height: 100%;
        background: $yellow;
        transition: width .25s ease;
    }
}
.ob-text-btn {
    min-height: 44px;
    padding: 0 10px;
    border: 0;
    background: transparent;
    color: $sub;
    font: inherit;
    font-size: 14px;
    cursor: pointer;
}

/* ── 본문 ── */
.ob-main {
    flex: 1;
    width: 100%;
    max-width: 560px;
    margin: 0 auto;
    padding: 20px 16px 24px;
    box-sizing: border-box;
}
.ob-count { margin: 0 0 8px; font-size: 13px; color: $accent; font-weight: 600; font-variant-numeric: tabular-nums; }
.ob-q, .ob-title {
    margin: 0 0 24px;
    font-size: 22px;
    line-height: 1.4;
    font-weight: 700;
    letter-spacing: -.3px;
    word-break: keep-all;
}
.ob-title { margin-bottom: 8px; }
.ob-lead { margin: 0 0 20px; font-size: 15px; line-height: 1.6; color: $sub; word-break: keep-all; b { color: $ink; } }

.ob-options, .ob-types { margin: 0; padding: 0; list-style: none; border-top: 1px solid $line; }

// 선택지: 카드 없이 흰 배경 위 구분선 목록. 고른 줄은 글자색과 ✓ 로만 표시한다.
.ob-option, .ob-type {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 60px;
    padding: 14px 4px;
    border: 0;
    border-bottom: 1px solid $line;
    background: transparent;
    color: $ink;
    text-align: left;
    font: inherit;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
    transition: background-color .15s ease;

    // 터치 기기에서는 :hover 가 탭한 자리에 남아, 다음 질문의 같은 위치 선택지가 골라진 것처럼 보인다 → 마우스에서만
    @media (hover: hover) { &:hover { background: $bg; } }
    &:active { background: $bar; }
    &.on { color: $brown-ink; }
    &.on .ob-option-label, &.on .t-name { font-weight: 700; }
}
.ob-option-label { font-size: 17px; line-height: 1.45; word-break: keep-all; }
.ob-check { flex: none; width: 20px; text-align: center; font-size: 18px; font-weight: 700; color: $accent; }

.ob-type {
    align-items: flex-start;
    &.compact { min-height: 56px; }
    .ob-check { padding-top: 2px; }
}
.t-body { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.t-name-line { display: flex; align-items: baseline; gap: 6px; }
.t-name { font-size: 17px; font-weight: 600; }
.t-mark { font-size: 13px; font-weight: 700; color: $accent; }
.t-desc { font-size: 14px; line-height: 1.5; color: $sub; word-break: keep-all; }
.t-stop { font-size: 13px; color: $sub-2; font-variant-numeric: tabular-nums; }

.ob-mode { margin-top: 28px; }
.ob-sub { margin: 0 0 8px; font-size: 15px; font-weight: 700; color: $ink; }
.ob-note { margin: 20px 0 0; font-size: 13px; line-height: 1.5; color: $sub-2; }

/* ── 하단 확정 버튼 ── */
.ob-foot {
    position: sticky;
    bottom: 0;
    width: 100%;
    max-width: 560px;
    margin: 0 auto;
    padding: 12px 16px calc(12px + env(safe-area-inset-bottom, 0px));
    box-sizing: border-box;
    background: linear-gradient(to bottom, rgba(255, 255, 255, 0), $card 24%);
}
.ob-cta {
    width: 100%;
    min-height: 52px;
    border: 0;
    border-radius: 14px;
    background: $yellow;
    color: #3A200F;
    font: inherit;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
    transition: transform .1s ease;
    &:active { transform: scale(.98); }
}

/* 질문 전환: 짧은 페이드 + 살짝 올라오기. 움직임 줄이기 설정이면 끈다. */
.ob-fade-enter-active, .ob-fade-leave-active { transition: opacity .18s ease, transform .18s ease; }
.ob-fade-enter-from { opacity: 0; transform: translateY(6px); }
.ob-fade-leave-to { opacity: 0; }
@media (prefers-reduced-motion: reduce) {
    .ob-fade-enter-active, .ob-fade-leave-active { transition: none; }
    .ob-progress i { transition: none; }
}
</style>
