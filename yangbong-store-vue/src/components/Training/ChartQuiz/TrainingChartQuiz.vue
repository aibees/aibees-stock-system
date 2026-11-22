<template>
    <div id="chart-quiz" class="cq-page">
        <header class="cq-head">
            <button type="button" class="cq-close" aria-label="닫기" @click="close">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
            </button>
            <span class="cq-brand">TRAINING</span>
            <span v-if="!retryId && quota" class="cq-progress" role="img" :aria-label="`오늘 ${progressFilled}문제 풀었어요`">
                <HexMark v-for="i in progressCount" :key="i" :size="13" :fill="i <= progressFilled ? 'var(--honey)' : '#E2DACA'" />
                <small v-if="quota.isSubscriber && quota.used > 3">+{{ quota.used - 3 }}</small>
            </span>
        </header>

        <main class="cq-main">
            <!-- 비로그인 -->
            <section v-if="!loggedIn" class="cq-empty">
                <HexMark :size="38" fill="var(--honey-line)" />
                <h2>로그인하고 차트를 읽어 보세요</h2>
                <p>실제 과거 차트를 보고 20일 뒤를 예상한 다음, 실제로 어떻게 움직였는지 맞춰 보는 연습이에요. 하루 3문제를 무료로 풀 수 있어요.</p>
                <button type="button" class="cq-btn honey" @click="goLogin">로그인</button>
            </section>

            <p v-else-if="loading" class="cq-msg">문제를 불러오고 있어요</p>

            <section v-else-if="loadError" class="cq-empty">
                <h2>{{ loadError }}</h2>
                <button type="button" class="cq-btn invert" @click="router.push(backPath)">돌아가기</button>
            </section>

            <!-- 문제 -->
            <template v-else-if="q && !result">
                <section class="cq-base">
                    <div>
                        <p class="cq-price">{{ q.basePrice.toFixed(1) }}
                            <span :class="dirCls(q.baseChangeRate)">{{ arrow(q.baseChangeRate) }} {{ signed(q.baseChangeRate) }}</span>
                        </p>
                        <p class="cq-label">기준가 100 기준</p>
                    </div>
                    <span class="cq-level">{{ levelText(q) }}</span>
                </section>

                <section class="cq-card">
                    <QuizChart :candles="q.snapshot.candles" :indicators="q.snapshot.indicators" :on="on" />
                </section>

                <div class="cq-chips" role="group" aria-label="지표 켜고 끄기">
                    <button v-for="it in INDICATORS" :key="it.key" type="button" class="cq-chip" :class="{ on: on.includes(it.key) }"
                        :aria-pressed="on.includes(it.key)" @click="toggle(it.key)">{{ it.label }}</button>
                </div>

                <section class="cq-ask">
                    <h2>20일 뒤, 어느 쪽일까요?</h2>
                    <button v-if="!hint" type="button" class="cq-hint-btn" :disabled="hintLoading" @click="openHint">힌트 보기 · 점수 20% 차감</button>
                    <p v-else class="cq-hint" aria-live="polite">{{ hint }}</p>
                </section>

                <div class="cq-choices">
                    <button v-for="c in CHOICES" :key="c.key" type="button" class="cq-choice" :class="c.key.toLowerCase()"
                        :disabled="submitting" @click="answer(c.key)">
                        <i aria-hidden="true">{{ c.icon }}</i>{{ c.label }}
                    </button>
                </div>
            </template>

            <!-- 결과 -->
            <template v-else-if="q && result">
                <section class="cq-verdict" aria-live="polite">
                    <HexMark :size="38" fill="var(--honey-line)" class="mark" />
                    <div>
                        <h2>{{ matchText(result.isMatch) }}</h2>
                        <p>내 선택 {{ choiceLabel(picked) }} · 20일 뒤 실제 {{ signed(result.outcome.returnRate) }}</p>
                        <p v-if="result.isMatch && !result.usedHint" class="sub">힌트 없이 맞춤</p>
                    </div>
                    <span v-if="result.honeyGained > 0" class="pts">+{{ result.honeyGained }}꿀</span>
                </section>

                <section class="cq-card">
                    <QuizChart :candles="q.snapshot.candles" :indicators="q.snapshot.indicators" :future="result.futureCandles"
                        :future-indicators="result.futureIndicators" :on="on" />
                </section>

                <section class="cq-nums">
                    <div><small>20일 뒤</small><b :class="dirCls(result.outcome.returnRate)">{{ arrow(result.outcome.returnRate) }} {{ signed(result.outcome.returnRate) }}</b></div>
                    <div class="key"><small>가는 길 최저</small><b :class="dirCls(result.outcome.maxDrawdown)">{{ arrow(result.outcome.maxDrawdown) }} {{ signed(result.outcome.maxDrawdown) }}</b></div>
                    <div><small>최고</small><b :class="dirCls(result.outcome.maxGain)">{{ arrow(result.outcome.maxGain) }} {{ signed(result.outcome.maxGain) }}</b></div>
                </section>

                <section class="cq-explain">
                    <h3><HexMark :size="15" fill="var(--honey)" />무슨 일이 있었나</h3>
                    <p>{{ result.explanation }}</p>
                </section>

                <section v-if="stat" class="cq-stat">
                    <h3>{{ result.pattern.name }}</h3>
                    <ul>
                        <li><small>발생</small><b>{{ stat.occurrences.toLocaleString() }}번</b></li>
                        <li><small>상승</small><b class="up">{{ stat.upCount.toLocaleString() }}번</b></li>
                        <li><small>하락</small><b class="down">{{ stat.downCount.toLocaleString() }}번</b></li>
                    </ul>
                    <div class="bar" role="img" :aria-label="`${stat.occurrences}번 중 상승 ${stat.upCount}번, 보합 ${stat.flatCount}번, 하락 ${stat.downCount}번`">
                        <i class="up" :style="{ width: pct(stat.upCount) }"></i>
                        <i class="flat" :style="{ width: pct(stat.flatCount) }"></i>
                        <i class="down" :style="{ width: pct(stat.downCount) }"></i>
                    </div>
                    <p class="legend">20일 뒤 +5% 이상은 상승, -5% 이하는 하락, 그 사이는 보합으로 셌어요.</p>
                    <p class="note">최근 1년 기록이에요. 앞으로도 같다는 뜻은 아니에요.</p>
                    <button type="button" class="cases" @click="openCases">
                        이 패턴 사례 {{ stat.occurrences.toLocaleString() }}건 전체 보기
                        <svg v-if="result.pattern.caseListLocked" viewBox="0 0 24 24" aria-label="구독 전용"><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>
                    </button>
                </section>

                <div class="cq-cta">
                    <button type="button" class="cq-btn honey" @click="router.push('/stock/preset')">이 조건 내 기준에 넣기</button>
                    <button type="button" class="cq-btn invert" @click="next">{{ nextLabel }}</button>
                </div>

                <p class="cq-fine">실제 과거 데이터예요. 수수료와 세금은 넣지 않았고, 특정 종목의 매매를 권하는 내용이 아니에요.</p>
            </template>

            <!-- 오늘 몫을 다 푼 뒤 / 문제가 없을 때 -->
            <section v-else class="cq-empty">
                <HexMark :size="38" fill="var(--honey-line)" />
                <template v-if="quota && quota.used > 0">
                    <h2>오늘 문제를 다 풀었어요</h2>
                    <p>{{ summaryText }}</p>
                </template>
                <template v-else>
                    <h2>문제를 준비하고 있어요</h2>
                    <p>매일 장이 끝난 뒤 새 문제가 만들어져요. 잠시 후 다시 열어 주세요.</p>
                </template>
                <button type="button" class="cq-btn invert" @click="router.push(backPath)">트레이닝으로</button>
            </section>
        </main>

        <!-- 무료 3문제를 다 썼을 때 -->
        <div v-if="sheet" class="cq-sheet-bg" @click.self="sheet = null">
            <section class="cq-sheet" role="dialog" aria-modal="true" aria-labelledby="cq-sheet-title">
                <HexMark :size="38" fill="var(--honey-line)" />
                <h2 id="cq-sheet-title">{{ sheet === 'quota' ? '오늘 무료 문제를 다 풀었어요' : '구독하면 열려요' }}</h2>
                <p v-if="sheet === 'quota'">무료는 하루 3문제예요. 구독하면 문제 수 제한 없이, Lv.3~4 문제와 지난 문제 다시 풀기까지 쓸 수 있어요.</p>
                <p v-else>이 패턴의 과거 사례 전체와 지난 문제 다시 풀기는 구독하면 볼 수 있어요.</p>
                <button type="button" class="cq-btn honey" @click="subscribe">구독하기</button>
                <button type="button" class="cq-btn ghost" @click="sheet === 'quota' ? close() : (sheet = null)">{{ sheet === 'quota' ? '내일 다시 오기' : '닫기' }}</button>
            </section>
        </div>
    </div>
</template>

<script setup>
/**
 * 트레이닝 차트 퀴즈(문제 → 결과). 명세: meetings/설계_2026-11-22_트레이닝-화면.md 3장(A안 벌집 라이트).
 *  - 기본: 오늘 세트(/training/today)를 차례로 푼다. 무료는 하루 3문제, 다 풀면 구독 안내.
 *  - ?q=<id>: 다시 풀기(구독). 점수는 처음 푼 기록만 남는다.
 *  - 힌트는 누르기 전에는 신호 설명을 전혀 보여 주지 않는다.
 * 구독: 결제가 아직 없어 꿀의 프리미엄 하루 이용권이 구독을 대신한다(서버 router_training_chart._is_subscriber) — "구독하기"는 꿀 화면으로 간다.
 */
import { assUserSession } from '@scripts/stores/user-stores';
import { useHoneyStore } from '@scripts/stores/honey-store.js';
import { rememberAfterLogin } from '@scripts/authPaths.js';
import { TRAINING_PATH } from '@scripts/training.js';
import {
    CHART_QUIZ_REVIEW_PATH, INDICATORS, CHOICES, levelText, matchText, choiceLabel, signed,
    loadToggles, saveToggles, fetchToday, fetchQuestion, fetchHint, submitAnswer, errorCode,
} from '@scripts/trainingChart.js';
import QuizChart from './QuizChart.vue';
import HexMark from './HexMark.vue';

const router = useRouter();
const route = useRoute();
const loggedIn = computed(() => !!assUserSession().user.accessToken);

const retryId = computed(() => (route.query.q ? Number(route.query.q) : null));
const backPath = computed(() => (retryId.value ? CHART_QUIZ_REVIEW_PATH : TRAINING_PATH));

const loading = ref(false);
const loadError = ref('');
const queue = ref([]);          // 오늘 아직 안 푼 문제들
const q = ref(null);
const quota = ref(null);
const totalScore = ref(0);
const result = ref(null);
const picked = ref(null);
const hint = ref('');
const hintLoading = ref(false);
const submitting = ref(false);
const sheet = ref(null);        // 'quota' | 'cases'
const sessionScore = ref(0);      // 이번에 받은 꿀 합
const sessionMatch = ref(0);
const sessionCount = ref(0);

const on = ref(loadToggles() ?? ['MA']);
const toggle = (k) => {
    on.value = on.value.includes(k) ? on.value.filter(x => x !== k) : INDICATORS.map(i => i.key).filter(x => x === k || on.value.includes(x));
    saveToggles(on.value);
};
const setQuestion = (next) => {
    q.value = next;
    result.value = null;
    picked.value = null;
    hint.value = '';
    // 이 세션에서 처음 보는 문제면 그 Lv 의 기본 켜짐, 한 번이라도 만졌으면 그 상태를 이어 간다
    if (next && !loadToggles()) on.value = [...next.defaultIndicators];
    window.scrollTo(0, 0);
};

const progressCount = computed(() => (quota.value?.isSubscriber ? 3 : quota.value?.dailyLimit ?? 3));
const progressFilled = computed(() => Math.min(progressCount.value, quota.value?.used ?? 0));

const load = async () => {
    if (!loggedIn.value) return;
    loading.value = true;
    loadError.value = '';
    try {
        if (retryId.value) {
            setQuestion(await fetchQuestion(retryId.value));
            return;
        }
        const d = await fetchToday();
        quota.value = d.quota;
        totalScore.value = d.totalScore ?? 0;
        queue.value = d.questions ?? [];
        setQuestion(queue.value[0] ?? null);
    } catch (e) {
        const code = errorCode(e);
        if (code === 'SUBSCRIPTION_REQUIRED') { loadError.value = '구독하면 지난 문제를 다시 풀 수 있어요.'; sheet.value = 'cases'; }
        else if (code === 'NOT_READY') loadError.value = '트레이닝 문제를 준비하고 있어요.';
        else if (code === 'NOT_FOUND') loadError.value = '문제를 찾을 수 없어요.';
        else loadError.value = '문제를 불러오지 못했어요. 잠시 후 다시 열어 주세요.';
    } finally {
        loading.value = false;
    }
};
onMounted(load);
watch(retryId, load);

const openHint = async () => {
    hintLoading.value = true;
    try {
        hint.value = (await fetchHint(q.value.questionId))?.hint || '';
    } catch {
        hint.value = '';
    } finally {
        hintLoading.value = false;
    }
};

const answer = async (key) => {
    if (submitting.value) return;
    submitting.value = true;
    picked.value = key;
    try {
        const r = await submitAnswer(q.value.questionId, key, !!hint.value);
        result.value = r;
        if (r.quota) quota.value = r.quota;
        totalScore.value = r.totalScore ?? totalScore.value;
        if (!r.retry) {
            sessionCount.value += 1;
            sessionScore.value += r.honeyGained ?? 0;
            if (r.honeyGained > 0) useHoneyStore().gainedElsewhere(r.honeyGained);
            if (r.isMatch) sessionMatch.value += 1;
        }
        queue.value = queue.value.filter(x => x.questionId !== q.value.questionId);
        window.scrollTo(0, 0);
    } catch (e) {
        picked.value = null;
        alert(errorCode(e) === 'SUBSCRIPTION_REQUIRED' ? '구독하면 이 문제를 풀 수 있어요.' : '답을 보내지 못했어요. 잠시 후 다시 눌러 주세요.');
    } finally {
        submitting.value = false;
    }
};

const nextLabel = computed(() => (retryId.value ? '목록으로' : '다음 문제'));
const next = async () => {
    if (retryId.value) { router.push(CHART_QUIZ_REVIEW_PATH); return; }
    const nid = result.value?.nextQuestionId;
    const inQueue = queue.value.find(x => x.questionId === nid) ?? queue.value[0];
    if (inQueue) { setQuestion(inQueue); return; }
    if (nid) {   // 구독자: 서버가 새로 붙인 문제
        try { setQuestion(await fetchQuestion(nid)); return; } catch { /* 아래로 */ }
    }
    if (quota.value && !quota.value.isSubscriber && quota.value.remaining === 0) sheet.value = 'quota';
    setQuestion(null);
};

const stat = computed(() => {
    const s = result.value?.pattern?.stat;
    return s && s.occurrences > 0 ? s : null;
});
const pct = (n) => `${stat.value ? (n / stat.value.occurrences) * 100 : 0}%`;
const openCases = () => {
    if (result.value?.pattern?.caseListLocked) { sheet.value = 'cases'; return; }
    alert('패턴 사례 목록은 패턴 아카이브와 함께 열릴 예정이에요.');
};

const summaryText = computed(() => {
    if (!sessionCount.value) return '내일 새 문제가 기다리고 있어요.';
    const honey = sessionScore.value > 0 ? ` 꿀 ${sessionScore.value}개를 모았어요.` : '';
    return `${sessionCount.value}문제 중 ${sessionMatch.value}번 같은 방향을 봤어요.${honey}`;
});

const dirCls = (n) => (n > 0 ? 'up' : n < 0 ? 'down' : 'flat');
const arrow = (n) => (n > 0 ? '▲' : n < 0 ? '▼' : '─');

const close = () => router.push(backPath.value);
const goLogin = () => { rememberAfterLogin(route.fullPath); router.push('/login'); };
const subscribe = () => router.push('/honey');
</script>

<style scoped lang="scss">
/* A안 벌집 라이트 토큰(명세 2장). 이 화면 안에서만 쓴다 — B안(다크)은 다크모드 테마로 따로 흡수한다. */
.cq-page {
    --bg-page: #FAF7F0;
    --bg-card: #FFFFFF;
    --bg-panel: #F4EFE2;
    --bg-invert: #2A2419;
    --line-card: #EDE6D6;
    --line-soft: #EFEADC;
    --line-chip: #E6DFCF;
    --line-chip-on: #DFC98C;
    --text-strong: #2A2419;
    --text-body: #443D2E;
    --text-muted: #8A7F6A;
    --text-faint: #A1927A;
    --text-invert: #FDF8EC;
    --honey: #D99800;
    --honey-soft: #F6EDD6;
    --honey-line: #F2B01E;
    --up: #C23E29;
    --up-chart: #D64530;
    --up-line: #E8BDB2;
    --flat: #6B6252;
    --flat-line: #DFD8C8;
    --down: #2B6090;
    --down-chart: #2F6FA8;
    --down-line: #B4CBE2;
    --ma5: #D99800;
    --ma20: #3F8F63;
    --ma60: #8A7BC8;

    min-height: 100vh;
    background: var(--bg-page);
    color: var(--text-body);
    text-align: left;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
    letter-spacing: -0.2px;
    -webkit-font-smoothing: antialiased;
}
button { border: 0; background: none; color: inherit; font: inherit; letter-spacing: inherit; cursor: pointer; -webkit-tap-highlight-color: transparent; }
.up { color: var(--up); }
.down { color: var(--down); }
.flat { color: var(--flat); }

.cq-head {
    position: sticky;
    top: env(safe-area-inset-top, 0px);
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 6px;
    height: 52px;
    padding: 0 18px 0 8px;
    background: var(--bg-page);
}
.cq-close {
    width: 40px; height: 40px;
    display: inline-flex; align-items: center; justify-content: center;
    svg { width: 20px; height: 20px; fill: none; stroke: var(--text-strong); stroke-width: 2.2; stroke-linecap: round; }
}
.cq-brand { flex: 1; font-size: 12px; font-weight: 800; letter-spacing: 1.4px; color: var(--text-strong); }
.cq-progress { display: inline-flex; align-items: center; gap: 4px; small { font-size: 11px; font-weight: 700; color: var(--text-muted); } }

.cq-main { max-width: 520px; margin: 0 auto; padding: 4px 18px 32px; box-sizing: border-box; }
.cq-msg { padding: 80px 0; text-align: center; font-size: 14px; color: var(--text-muted); }

.cq-base {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
    margin: 6px 0 12px;
}
.cq-price {
    margin: 0;
    font-size: 34px;
    font-weight: 800;
    letter-spacing: -1px;
    color: var(--text-strong);
    font-variant-numeric: tabular-nums;
    span { margin-left: 6px; font-size: 14px; font-weight: 700; letter-spacing: -0.2px; }
}
.cq-label { margin: 2px 0 0; font-size: 11px; font-weight: 600; color: var(--text-muted); }
.cq-level {
    flex: none;
    margin-top: 8px;
    padding: 6px 10px;
    border-radius: 9px;
    background: var(--honey-soft);
    font-size: 11px;
    font-weight: 700;
    color: var(--text-body);
}

.cq-card {
    padding: 14px;
    border: 1px solid var(--line-card);
    border-radius: 18px;
    background: var(--bg-card);
}

.cq-chips {
    display: flex;
    gap: 6px;
    margin-top: 10px;
    overflow-x: auto;
    scrollbar-width: none;
    &::-webkit-scrollbar { display: none; }
}
.cq-chip {
    flex: none;
    height: 32px;
    padding: 0 12px;
    border: 1px solid var(--line-chip);
    border-radius: 9px;
    background: var(--bg-card);
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    &.on { border-color: var(--line-chip-on); background: var(--honey-soft); color: var(--text-strong); }
}

.cq-ask {
    margin: 22px 0 12px;
    h2 { margin: 0; font-size: 20px; font-weight: 800; letter-spacing: -0.5px; color: var(--text-strong); }
}
.cq-hint-btn {
    margin-top: 6px;
    padding: 4px 0;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-decoration: underline;
    text-underline-offset: 3px;
    &:disabled { opacity: .5; }
}
.cq-hint {
    margin: 10px 0 0;
    padding: 12px 14px;
    border-radius: 13px;
    background: var(--bg-panel);
    font-size: 14px;
    line-height: 1.65;
    word-break: keep-all;
}

.cq-choices { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.cq-choice {
    height: 64px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    border: 1.5px solid var(--line-chip);
    border-radius: 14px;
    background: var(--bg-card);
    font-size: 15px;
    font-weight: 700;
    color: var(--text-strong);
    i { font-style: normal; font-size: 13px; line-height: 1; }
    &.up i { color: var(--up); }
    &.flat i { color: var(--flat); }
    &.down i { color: var(--down); }
    &:active { background: var(--honey-soft); border-color: var(--line-chip-on); }
    &:disabled { opacity: .6; cursor: default; }
}

/* 결과 */
.cq-verdict {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 6px 0 12px;
    padding: 16px;
    border-radius: 18px;
    background: var(--bg-invert);
    color: var(--text-invert);
    .mark { flex: none; }
    div { flex: 1; min-width: 0; }
    h2 { margin: 0; font-size: 18px; font-weight: 800; letter-spacing: -0.4px; }
    p { margin: 3px 0 0; font-size: 12px; font-weight: 600; opacity: .78; }
    .sub { color: var(--honey-line); opacity: 1; }
    .pts { flex: none; font-size: 14px; font-weight: 800; color: var(--honey-line); font-variant-numeric: tabular-nums; }
}

.cq-nums {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    margin-top: 10px;
    div { padding: 12px 10px; border: 1px solid var(--line-card); border-radius: 14px; background: var(--bg-card); }
    .key { border-color: var(--line-chip-on); }
    small { display: block; font-size: 11px; font-weight: 600; color: var(--text-muted); }
    b { display: block; margin-top: 4px; font-size: 16px; font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: -0.4px; }
}

.cq-explain {
    margin-top: 22px;
    h3 { display: flex; align-items: center; gap: 6px; margin: 0 0 6px; font-size: 15px; font-weight: 800; color: var(--text-strong); }
    p { margin: 0; font-size: 14px; line-height: 1.65; word-break: keep-all; }
}

.cq-stat {
    margin-top: 20px;
    padding: 16px 14px;
    border-radius: 18px;
    background: var(--bg-panel);
    h3 { margin: 0 0 10px; font-size: 14px; font-weight: 800; color: var(--text-strong); }
    ul { display: flex; gap: 18px; margin: 0; padding: 0; list-style: none; }
    small { display: block; font-size: 11px; font-weight: 600; color: var(--text-muted); }
    b { font-size: 16px; font-weight: 800; font-variant-numeric: tabular-nums; color: var(--text-strong); &.up { color: var(--up); } &.down { color: var(--down); } }
    .bar { display: flex; height: 8px; margin-top: 12px; border-radius: 4px; overflow: hidden; background: var(--flat-line); }
    .bar i { display: block; height: 100%; }
    .bar .up { background: var(--up-chart); }
    .bar .flat { background: var(--flat-line); }
    .bar .down { background: var(--down-chart); }
    .legend { margin: 8px 0 0; font-size: 11px; color: var(--text-muted); line-height: 1.5; }
    .note { margin: 4px 0 0; font-size: 12px; font-weight: 600; color: var(--text-body); }
    .cases {
        display: inline-flex; align-items: center; gap: 4px;
        margin-top: 12px; padding: 4px 0;
        font-size: 13px; font-weight: 700; color: var(--text-strong);
        svg { width: 14px; height: 14px; fill: none; stroke: var(--text-muted); stroke-width: 2; stroke-linecap: round; }
    }
}

.cq-cta { display: flex; flex-direction: column; gap: 8px; margin-top: 22px; }
.cq-btn {
    width: 100%;
    min-height: 52px;
    border-radius: 14px;
    font-size: 16px;
    font-weight: 800;
    &.honey { background: var(--honey); color: #FFFFFF; }
    &.invert { background: var(--bg-invert); color: var(--text-invert); }
    &.ghost { background: transparent; color: var(--text-muted); font-weight: 700; }
}
.cq-fine { margin: 18px 0 0; font-size: 11px; line-height: 1.6; color: var(--text-faint); word-break: keep-all; }

.cq-empty {
    padding: 64px 4px 0;
    text-align: center;
    h2 { margin: 14px 0 0; font-size: 20px; font-weight: 800; letter-spacing: -0.5px; color: var(--text-strong); }
    p { margin: 8px 0 22px; font-size: 14px; line-height: 1.65; color: var(--text-muted); word-break: keep-all; }
}

.cq-sheet-bg {
    position: fixed;
    inset: 0;
    z-index: 100;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    background: rgba(42, 36, 25, .42);
}
.cq-sheet {
    width: 100%;
    max-width: 520px;
    padding: 24px 18px calc(18px + env(safe-area-inset-bottom, 0px));
    border-radius: 18px 18px 0 0;
    background: var(--bg-page);
    text-align: center;
    box-sizing: border-box;
    h2 { margin: 12px 0 0; font-size: 18px; font-weight: 800; color: var(--text-strong); }
    p { margin: 8px 0 18px; font-size: 14px; line-height: 1.65; color: var(--text-muted); word-break: keep-all; }
    .cq-btn + .cq-btn { margin-top: 6px; }
}
</style>
