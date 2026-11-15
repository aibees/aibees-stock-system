<template>
    <div id="training-home">
        <header class="tr-header">
            <h1>트레이닝</h1>
            <p class="tr-lead">차트와 기업을 보는 법을 순서대로 익혀 보세요.</p>
        </header>

        <main class="tr-main">
            <section v-for="(g, gi) in groups" :key="gi" class="tr-group" :class="{ soon: g.courses.every(c => c.soon) }">
                <h2 v-if="g.title">{{ g.title }}</h2>
                <ul class="tr-list">
                    <li v-for="c in g.courses" :key="c.slug">
                        <div v-if="c.soon" class="tr-row off">
                            <span class="tr-name">{{ c.name }}</span>
                            <span class="tr-soon">준비 중</span>
                        </div>
                        <button v-else type="button" class="tr-row" @click="open(c)">
                            <span class="tr-text">
                                <span class="tr-name">{{ c.name }}</span>
                                <span class="tr-sum">{{ c.summary }}</span>
                            </span>
                            <svg class="chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="m9 6 6 6-6 6"></path></svg>
                        </button>
                    </li>
                </ul>
            </section>

            <p class="tr-note">설명용 자료이며 특정 종목의 매수·매도를 권하지 않습니다. 투자 판단과 책임은 본인에게 있습니다.</p>
        </main>
    </div>
</template>

<script setup>
import { trainingGroups, TRAINING_PATH } from '@scripts/training.js';

const router = useRouter();
const groups = trainingGroups();
const open = (c) => router.push(`${TRAINING_PATH}/${c.slug}`);
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

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
.tr-main { max-width: 720px; margin: 0 auto; padding: 8px 0 24px; }
.tr-group {
    h2 { margin: 18px 16px 4px; font-size: .8rem; font-weight: 700; color: $accent; letter-spacing: .02em; }
    &.soon h2 { color: $sub-2; }
}
.tr-list { list-style: none; margin: 0; padding: 0; }
.tr-list li + li .tr-row { border-top: 1px solid $line-soft; }
.tr-row {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 16px;
    min-height: 52px;
    box-sizing: border-box;
    background: none;
    border: 0;
    font: inherit;
    color: inherit;
    text-align: left;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;

    &:hover { background: #FFFDF3; }
    &.off { cursor: default; &:hover { background: none; } }
}
.tr-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.tr-name { font-size: 1rem; font-weight: 700; }
.tr-sum { font-size: .82rem; color: $sub; line-height: 1.4; }
.tr-row.off .tr-name { color: $sub-2; font-weight: 600; }
.tr-soon { font-size: .8rem; color: $sub-2; white-space: nowrap; }
.chev { color: $sub-2; flex-shrink: 0; }
.tr-note { margin: 20px 16px 0; font-size: .76rem; line-height: 1.5; color: $sub-2; }
</style>
