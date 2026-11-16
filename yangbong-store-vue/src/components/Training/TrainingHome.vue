<template>
    <div id="training-home">
        <header class="tr-header">
            <h1>트레이닝</h1>
            <p class="tr-lead">차트와 기업을 보는 법을 순서대로 익혀 보세요.</p>
        </header>

        <main class="tr-main">
            <!-- 진행 카드 -->
            <section class="tr-card tr-progress" aria-label="진행 상황">
                <div class="tr-progress-row">
                    <span class="tr-progress-label">완료한 단계</span>
                    <span class="tr-progress-count"><b>{{ store.doneCount }}</b> / {{ store.total }}</span>
                </div>
                <div class="tr-bar" role="progressbar" aria-label="완료한 단계"
                    :aria-valuenow="store.doneCount" aria-valuemin="0" :aria-valuemax="store.total">
                    <span :style="{ width: `${pct}%` }"></span>
                </div>
                <p class="tr-progress-note">{{ next ? '앞 단계를 마쳐야 다음 단계가 열려요' : '✓ 모든 단계를 마쳤어요' }}</p>
            </section>

            <!-- 장 카드: 안에 단계를 2열 칸으로 -->
            <section v-for="ch in chapterList" :id="`ch-${ch.slug}`" :key="ch.slug" class="tr-card tr-chapter">
                <div class="tr-ch-head">
                    <span class="tr-dot" :class="{ on: chapterState(ch).cls !== 'locked' }" aria-hidden="true"></span>
                    <div class="tr-ch-text">
                        <p class="tr-ch-meta">{{ ch.no }}장 · 단계 {{ ch.first }}–{{ ch.last }}</p>
                        <h2>{{ ch.name }}</h2>
                    </div>
                    <span class="tr-pill" :class="chapterState(ch).cls">
                        <svg v-if="chapterState(ch).cls === 'locked'" width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 10V7a5 5 0 0 1 10 0v3h1a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h1zm2 0h6V7a3 3 0 0 0-6 0v3z"></path></svg>
                        {{ chapterState(ch).text }}
                    </span>
                </div>

                <ol class="tr-grid">
                    <li v-for="s in ch.stages" :key="s.key">
                        <button v-if="store.isOpen(s.key)" type="button" class="tr-tile"
                            :class="{ done: store.isDone(s.key), next: isNext(s) }"
                            :aria-label="`${s.no}단계 ${s.title}${store.isDone(s.key) ? ', 마침' : isNext(s) ? ', 지금 차례' : ''}`"
                            :title="s.title" @click="openStage(s)">
                            <span class="tr-ico" aria-hidden="true">
                                <svg v-if="store.isDone(s.key)" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"></path></svg>
                                <template v-else>{{ s.no }}</template>
                            </span>
                            <span class="tr-tile-label">{{ s.title }}</span>
                        </button>
                        <div v-else class="tr-tile locked" :aria-label="`${s.no}단계 ${s.title}, 잠김`" :title="s.title">
                            <span class="tr-ico" aria-hidden="true">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M7 10V7a5 5 0 0 1 10 0v3h1a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h1zm2 0h6V7a3 3 0 0 0-6 0v3z"></path></svg>
                            </span>
                            <span class="tr-tile-label">{{ s.title }}</span>
                        </div>
                    </li>
                </ol>
            </section>

            <section v-if="soon.length" class="tr-card tr-chapter tr-soon">
                <div class="tr-ch-head">
                    <span class="tr-dot" aria-hidden="true"></span>
                    <div class="tr-ch-text"><h2>곧 추가됩니다</h2></div>
                </div>
                <ul class="tr-grid">
                    <li v-for="name in soon" :key="name">
                        <div class="tr-tile locked" :title="name"><span class="tr-tile-label">{{ name }}</span></div>
                    </li>
                </ul>
            </section>

            <p class="tr-note">설명용 자료이며 특정 종목의 매수·매도를 권하지 않습니다. 투자 판단과 책임은 본인에게 있습니다.</p>
        </main>
    </div>
</template>

<script setup>
import { chapters, soonItems, stagePath } from '@scripts/training.js';
import { useTrainingStore } from '@scripts/stores/training-store.js';

const router = useRouter();
const store = useTrainingStore();

const chapterList = chapters();
const soon = soonItems();
const next = computed(() => store.nextStage);
const pct = computed(() => (store.total ? Math.round(store.doneCount / store.total * 100) : 0));

const isNext = (s) => next.value?.key === s.key;
const openStage = (s) => router.push(stagePath(s));

// 장 제목 오른쪽 표시: 마친 수 / 다 마침 / 잠김.
const chapterState = (ch) => {
    const n = ch.stages.filter(s => store.isDone(s.key)).length;
    if (n === ch.stages.length) return { text: '✓ 마침', cls: 'all' };
    if (!store.isOpen(ch.stages[0].key)) return { text: '잠김', cls: 'locked' };
    return { text: `${n}/${ch.stages.length}`, cls: 'now' };
};
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

// 레퍼런스(장 카드 + 2열 단계 칸) 배치를 양봉상회 색으로 옮긴 것.
$tint:      #FBF3E4;   // 진행 카드·지금 칸 아이콘 바탕
$pill:      #F6E8D2;
$off-bg:    #F2F1EE;   // 잠긴 칸
$off-ink:   #8F8A84;
$off-dot:   #D6D3CE;

#training-home {
    min-height: 100vh;
    background: $card;
    color: $ink;
    text-align: left;
    font-family: $font-body;
}
.tr-header {
    background: $bar;
    padding: 18px 16px 14px;
    border-bottom: 1px solid $line;
    position: sticky;
    top: env(safe-area-inset-top, 0px);
    z-index: 10;

    h1 { margin: 0; font-size: 1.2rem; font-weight: 800; color: $brown-ink; }
    .tr-lead { margin: 4px 0 0; font-size: .84rem; color: $sub; }
}
.tr-main { max-width: 720px; margin: 0 auto; padding: 14px 16px 24px; box-sizing: border-box; }

.tr-card {
    border: 1px solid $line;
    border-radius: 16px;
    background: $card;
    padding: 18px 16px;
    & + .tr-card { margin-top: 12px; }
}

/* ── 진행 카드 ── */
.tr-progress { background: $tint; }
.tr-progress-row { display: flex; align-items: baseline; justify-content: space-between; }
.tr-progress-label { font-size: .98rem; font-weight: 700; color: $sub; }
.tr-progress-count {
    font-size: 1rem; color: $sub-2; font-variant-numeric: tabular-nums;
    b { font-size: 1.7rem; font-weight: 800; color: $ink; margin-right: 2px; }
}
.tr-bar {
    height: 8px; margin: 12px 0 10px; border-radius: 4px; background: $line-soft; overflow: hidden;
    span { display: block; height: 100%; min-width: 8px; border-radius: 4px; background: $accent; transition: width .3s ease; }
}
.tr-progress-note { margin: 0; font-size: .84rem; color: $sub-2; }

/* ── 장 카드 ── */
.tr-ch-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.tr-dot {
    flex: none; width: 12px; height: 12px; border-radius: 50%; background: $off-dot; align-self: flex-end; margin-bottom: 6px;
    &.on { background: $accent; }
}
.tr-ch-text { flex: 1; min-width: 0; }
.tr-ch-meta { margin: 0 0 2px; font-size: .8rem; color: $sub-2; font-variant-numeric: tabular-nums; }
.tr-ch-head h2 { margin: 0; font-size: 1.15rem; font-weight: 800; color: $ink; word-break: keep-all; }
.tr-pill {
    flex: none; display: inline-flex; align-items: center; gap: 4px;
    padding: 5px 11px; border-radius: 999px;
    font-size: .82rem; font-weight: 700; font-variant-numeric: tabular-nums;
    &.now, &.all { background: $pill; color: $accent; }
    &.locked { background: $off-bg; color: $off-ink; font-weight: 600; }
}

/* ── 단계 칸: 2열 ── */
.tr-grid {
    list-style: none; margin: 0; padding: 0;
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px;
}
.tr-tile {
    width: 100%; height: 48px;
    display: flex; align-items: center; gap: 9px;
    padding: 0 10px; box-sizing: border-box;
    border: 1px solid $line-2; border-radius: 10px;
    background: $card; color: $ink;
    font: inherit; text-align: left;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
    transition: transform .1s ease;
    &:active:not(.locked) { transform: scale(.98); }

    &.done {
        background: $accent; border-color: $accent; color: #fff;
        .tr-ico { background: rgba(255, 255, 255, .22); color: #fff; }
        .tr-tile-label { font-weight: 700; }
    }
    &.next {
        border: 2px solid $accent; padding: 0 9px;
        .tr-tile-label { font-weight: 700; color: $brown-ink; }
    }
    &.locked {
        background: $off-bg; border-color: $off-bg; color: $off-ink; cursor: default;
        .tr-ico { background: #fff; color: #A8A39C; }
    }
}
.tr-ico {
    flex: none; width: 26px; height: 26px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    background: $tint; color: $accent;
    font-size: .8rem; font-weight: 800; font-variant-numeric: tabular-nums;
}
.tr-tile-label {
    flex: 1; min-width: 0;
    font-size: .9rem; font-weight: 600;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.tr-soon .tr-tile { padding-left: 14px; }

.tr-note { margin: 18px 4px 0; font-size: .76rem; line-height: 1.5; color: $sub-2; }
</style>
