<template>
    <div id="training-review">
        <BrandHeader :title="playing ? '복습하기' : '다시 보기'" :back="playing ? `${REVIEW_PATH}?tab=today` : TRAINING_PATH" />
        <main class="rv">
            <!-- ── 복습 풀기: 오늘 할 것만 한 장씩 ── -->
            <template v-if="playing">
                <p class="rv-count">{{ Math.min(pos + 1, queue.length) }} / {{ queue.length }}</p>
                <template v-if="cur">
                    <section v-if="cur.kind === 'wrong' && cur.question" class="card">
                        <p class="k wrong">오답 · {{ cur.label || cur.question.chapterName }}</p>
                        <p class="qq">{{ cur.question.q }}</p>
                        <button v-for="(opt, oi) in cur.question.options" :key="oi" type="button" class="opt" :class="optCls(oi)"
                            :disabled="picked != null" @click="pickOpt(oi)"><span>{{ opt }}</span><span aria-hidden="true">{{ optMark(oi) }}</span></button>
                        <p v-if="picked != null" class="fb" :class="{ right: picked === cur.question.answer }">
                            <b>{{ picked === cur.question.answer ? stepText(true) : '다시 처음부터 볼게요.' }}</b> {{ cur.question.explain }}
                        </p>
                    </section>
                    <section v-else-if="cur.kind === 'term'" class="card">
                        <p class="k term">헷갈린 용어 · {{ cur.label || '용어 사전' }}</p>
                        <p class="term-name">{{ cur.ref }}</p>
                        <p v-if="!shown" class="hint">뜻을 먼저 떠올려 본 뒤 눌러 보세요.</p>
                        <p v-else class="term-desc">{{ cur.desc || '용어 사전에서 뜻을 확인해 보세요.' }}</p>
                        <button v-if="!shown" type="button" class="btn ghost" @click="shown = true">뜻 보기</button>
                        <div v-else-if="judged == null" class="two">
                            <button type="button" class="btn ghost" @click="judgeTerm(false)">아직 헷갈려요</button>
                            <button type="button" class="btn" @click="judgeTerm(true)">알았어요</button>
                        </div>
                        <p v-else class="fb" :class="{ right: judged }"><b>{{ judged ? stepText(true) : '내일 다시 볼게요.' }}</b></p>
                    </section>
                    <button v-if="answered" type="button" class="btn next" @click="goNext">{{ pos + 1 < queue.length ? '다음' : '마치기' }}</button>
                </template>
                <section v-else class="done">
                    <img src="/img/emoji/trophy.png" alt="" width="56" height="56" />
                    <b>오늘 복습을 마쳤어요</b>
                    <p>맞힌 것은 다음 날짜에, 틀린 것은 내일 다시 나와요.</p>
                    <button type="button" class="btn" @click="router.replace({ path: REVIEW_PATH, query: { tab: 'today' } })">목록으로</button>
                </section>
            </template>

            <!-- ── 목록 ── -->
            <template v-else>
                <section class="top">
                    <b>{{ review.dueList.length ? `오늘 ${review.dueList.length}개` : '오늘 볼 것 없음' }}</b>
                    <p>틀린 문제와 헷갈린 용어를 1일 → 3일 → 7일 뒤에 다시 보여 드려요. 3번 연속 맞히면 목록에서 빠져요.</p>
                    <button v-if="review.dueList.length" type="button" class="btn" @click="begin">복습 시작하기</button>
                </section>
                <div class="tabs" role="tablist">
                    <button v-for="t in TABS" :key="t.key" type="button" role="tab" class="tab" :class="{ on: tab === t.key }"
                        :aria-selected="tab === t.key ? 'true' : 'false'" @click="setTab(t.key)">{{ t.label }} {{ countOf(t.key) }}</button>
                </div>
                <p v-if="!list.length" class="empty">{{ EMPTY[tab] }}</p>
                <ul v-else class="list">
                    <li v-for="it in list" :key="it.key" class="item">
                        <div class="ik"><b :class="it.kind">{{ it.kind === 'wrong' ? '오답' : '헷갈린 용어' }}</b><span>{{ it.label }}{{ it.label ? ' · ' : '' }}{{ dueText(it) }}</span></div>
                        <p class="it">{{ it.kind === 'wrong' ? (questionOf(it)?.q ?? '지금은 없는 문제예요') : it.ref }}</p>
                        <p v-if="it.kind === 'term' && it.desc" class="id">{{ it.desc }}</p>
                        <div class="row">
                            <span class="steps" :aria-label="`${it.step ?? 0}/3번 맞힘`"><i v-for="n in 3" :key="n" :class="{ f: (it.step ?? 0) >= n }"></i></span>
                            <button v-if="it.kind === 'term'" type="button" class="off" @click="review.toggleTerm(it.ref)">빼기</button>
                        </div>
                    </li>
                </ul>
                <p class="note">오답은 수업 속 퀴즈·장 끝 확인 퀴즈·퀴즈 모음·오늘의 한 문제에서 저절로 모여요. 헷갈린 용어는 수업과 용어 사전의 '헷갈려요'로 담아요.</p>
            </template>
        </main>
    </div>
</template>

<script setup>
/** 다시 보기(/training/review?tab=today|wrong|term): 복습하기 · 오답노트 · 헷갈린 용어. 기록: review-store.js */
import { TRAINING_PATH } from '@scripts/training.js';
import { findQuestion } from '@scripts/trainingQuiz.js';
import { useReviewStore, REVIEW_STEPS, GRADUATE_AT, REVIEW_PATH } from '@scripts/stores/review-store.js';

const route = useRoute();
const router = useRouter();
const review = useReviewStore();

const TABS = [{ key: 'today', label: '오늘 할 것' }, { key: 'wrong', label: '오답노트' }, { key: 'term', label: '헷갈린 용어' }];
const EMPTY = { today: '오늘 다시 볼 것은 없어요.', wrong: '틀린 문제가 없어요. 퀴즈에서 틀리면 여기 모여요.', term: "헷갈린 용어가 없어요. 수업이나 용어 사전에서 '헷갈려요'를 눌러 보세요." };
const tab = computed(() => (TABS.some(t => t.key === route.query.tab) ? route.query.tab : 'today'));
const setTab = (k) => router.replace({ path: REVIEW_PATH, query: { tab: k } });
const listOf = (k) => (k === 'wrong' ? review.wrongList : k === 'term' ? review.termList : review.dueList);
const list = computed(() => listOf(tab.value));
const countOf = (k) => listOf(k).length;
const questionOf = (it) => findQuestion(it.ref);
const dueText = (it) => {
    const days = Math.round((new Date(it.due).setHours(0, 0, 0, 0) - new Date().setHours(0, 0, 0, 0)) / 86400000);
    return days <= 0 ? '오늘 복습' : days === 1 ? '내일 복습' : `${days}일 뒤 복습`;
};

/* ── 복습 풀기 ── */
// 풀기 화면은 ?play=1 — 헤더의 ‹ 가 목록(?tab=today)으로 돌아간다
const playing = computed(() => route.query.play === '1');
const queue = ref([]);
const pos = ref(0);
const picked = ref(null);
const shown = ref(false);
const judged = ref(null);
const cur = computed(() => {
    const it = queue.value[pos.value];
    return it ? { ...it, question: it.kind === 'wrong' ? findQuestion(it.ref) : null } : null;
});
const answered = computed(() => picked.value != null || judged.value != null);
const start = () => {
    // 없어진 문제(목차가 바뀐 경우)는 건너뛴다
    queue.value = review.dueList.filter(it => it.kind === 'term' || findQuestion(it.ref)).map(it => ({ ...it }));
    pos.value = 0; picked.value = null; shown.value = false; judged.value = null;
    window.scrollTo(0, 0);
};
const begin = () => { start(); router.push({ path: REVIEW_PATH, query: { play: '1' } }); };
// 주소로 바로 들어오거나 새로고침하면 그때 오늘 할 것을 다시 모은다
watch(playing, (p) => { if (p && !queue.value.length) start(); }, { immediate: true });
const stepText = (right) => {
    if (!right) return '';
    const step = (cur.value?.step ?? 0) + 1;
    return step >= GRADUATE_AT ? '맞았어요! 이제 목록에서 빠져요.' : `맞았어요! ${REVIEW_STEPS[step]}일 뒤에 다시 볼게요.`;
};
const pickOpt = (oi) => {
    if (picked.value != null) return;
    picked.value = oi;
    review.answer(cur.value.key, oi === cur.value.question.answer);
};
const optCls = (oi) => (picked.value == null ? {} : { right: oi === cur.value.question.answer, wrong: oi === picked.value && oi !== cur.value.question.answer });
const optMark = (oi) => { const c = optCls(oi); return c.right ? '✓' : c.wrong ? '✕' : ''; };
const judgeTerm = (ok) => { judged.value = ok; review.answer(cur.value.key, ok); };
const goNext = () => {
    pos.value += 1; picked.value = null; shown.value = false; judged.value = null;
    window.scrollTo(0, 0);
};
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#training-review { min-height: 100vh; background: $card; color: $ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; }
button { font: inherit; letter-spacing: inherit; cursor: pointer; border: 0; }
.rv { max-width: 640px; margin: 0 auto; padding: 8px $pad-x $sec-pb; box-sizing: border-box; }
.top { padding: $card-pad; border-radius: $radius; background: $honey-strip;
    b { font-size: 22px; letter-spacing: -0.5px; } p { margin: 4px 0 0; font-size: 13.5px; line-height: 1.55; color: $sub-ink; word-break: keep-all; } .btn { margin-top: $gap; } }
.tabs { display: flex; gap: 8px; margin-top: $sec-pt; overflow-x: auto; }
.tab { flex: none; height: 36px; padding: 0 14px; border-radius: 10px; background: $band; color: $sub-ink; font-size: 14px; font-weight: 600;
    &.on { background: $honey-300; color: $honey-ink; } }
.empty { padding: 40px 0; text-align: center; font-size: 14px; color: $sub; line-height: 1.6; word-break: keep-all; }
.list { list-style: none; margin: $gap 0 0; padding: 0; }
.item { padding: 14px $card-pad; border: 1px solid $line; border-radius: $radius; & + .item { margin-top: $gap; } }
.ik { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; color: $sub;
    b { font-weight: 700; &.wrong { color: $up; } &.term { color: $amber-700; } } span { text-align: right; } }
.it { margin: 4px 0 0; font-size: 15px; font-weight: 700; line-height: 1.45; word-break: keep-all; }
.id { margin: 4px 0 0; font-size: 13px; line-height: 1.5; color: $sub-ink; }
.row { display: flex; align-items: center; gap: 12px; margin-top: 10px; }
.steps { flex: 1; display: flex; gap: 4px; i { flex: 1; height: 5px; border-radius: 3px; background: $band; &.f { background: $honey-500; } } }
.off { flex: none; height: 28px; padding: 0 10px; border-radius: 8px; background: $band; color: $sub-ink; font-size: 12.5px; font-weight: 600; }
.note { margin: $sec-pt 0 0; font-size: 12px; line-height: 1.6; color: $sub; word-break: keep-all; }

/* 풀기 */
.rv-count { margin: 0 0 $gap; font-size: 13px; color: $sub; font-variant-numeric: tabular-nums; }
.card { padding: $card-pad; border: 1.5px solid $line; border-radius: $radius; }
.k { margin: 0; font-size: 12px; font-weight: 700; &.wrong { color: $up; } &.term { color: $amber-700; } }
.qq { margin: 4px 0 4px; font-size: 16px; font-weight: 700; line-height: 1.5; word-break: keep-all; }
.opt { width: 100%; display: flex; justify-content: space-between; gap: 12px; margin-top: 8px; padding: 12px 14px; border: 1.5px solid $line; border-radius: 10px;
    background: $card; color: $ink; font-size: 14.5px; text-align: left; line-height: 1.45;
    &:disabled { cursor: default; } &.wrong { border-color: #F5B5BC; background: #FFF5F6; } &.right { border-color: #9BD6AE; background: #F2FBF5; } }
.fb { margin: 10px 0 0; padding: 12px 14px; border-radius: 10px; background: #FFF5F6; font-size: 13.5px; line-height: 1.6; color: $sub-ink;
    b { color: $up; } &.right { background: #F2FBF5; b { color: #1E7A3C; } } }
.term-name { margin: 8px 0 0; font-size: 26px; font-weight: 800; letter-spacing: -0.6px; }
.hint { margin: 8px 0 $gap; font-size: 14px; color: $sub; }
.term-desc { margin: 8px 0 $gap; font-size: 15.5px; line-height: 1.65; color: $sub-ink; word-break: keep-all; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: $gap; }
.btn { width: 100%; height: 52px; border-radius: $radius; background: #5A3C08; color: #fff; font-size: 16px; font-weight: 700;
    &.ghost { background: $band; color: $ink; } &.next { margin-top: $gap; } }
.done { padding: 40px 0; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 8px;
    b { font-size: 20px; } p { margin: 0 0 $gap; font-size: 14px; color: $sub-ink; } }
</style>
