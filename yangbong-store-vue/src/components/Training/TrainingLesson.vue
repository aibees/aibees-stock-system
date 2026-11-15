<template>
    <div id="training-lesson">
        <header class="tl-header">
            <button type="button" class="tl-back" aria-label="트레이닝 목차로" @click="router.push(TRAINING_PATH)">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg>
            </button>
            <h1>{{ course ? title : '찾을 수 없는 강의' }}</h1>
        </header>

        <main class="tl-main">
            <template v-if="course">
                <p class="tl-sum">{{ course.summary }}</p>

                <h2>목차</h2>
                <ol class="tl-chapters">
                    <li v-for="(ch, i) in course.chapters" :key="i">
                        <span class="tl-no">{{ i + 1 }}</span>
                        <span class="tl-title">{{ ch }}</span>
                    </li>
                </ol>

                <p class="tl-soon">본문은 준비 중입니다. 목차는 바뀔 수 있습니다.</p>
            </template>
            <template v-else>
                <p class="tl-sum">없거나 아직 열리지 않은 강의입니다.</p>
                <button type="button" class="tl-btn" @click="router.push(TRAINING_PATH)">목차로 돌아가기</button>
            </template>
        </main>
    </div>
</template>

<script setup>
import { findCourse, trainingGroups, TRAINING_PATH } from '@scripts/training.js';

const router = useRouter();
const route = useRoute();
const course = computed(() => findCourse(String(route.params.slug ?? '')));
// 같은 묶음 이름을 앞에 붙인다: "차트 보는 법 · 기초". 이름이 같으면(기업분석) 한 번만.
const title = computed(() => {
    const g = trainingGroups().find(x => x.courses.some(c => c.slug === course.value?.slug));
    return g && g.title && g.title !== course.value.name ? `${g.title} · ${course.value.name}` : course.value.name;
});
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#training-lesson {
    min-height: 100vh;
    background: $card;
    color: $ink;
    text-align: left;
    font-family: $font-body;
}
.tl-header {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px 6px 4px;
    background: $bar;
    border-bottom: 1px solid $line;
    position: sticky;
    top: env(safe-area-inset-top, 0px);
    z-index: 10;

    h1 { margin: 0; font-size: 1.05rem; font-weight: 800; color: $brown-ink; }
}
.tl-back {
    width: 44px; height: 44px;
    display: inline-flex; align-items: center; justify-content: center;
    background: none; border: 0; color: $brown-ink; cursor: pointer;
}
.tl-main { max-width: 720px; margin: 0 auto; padding: 16px 16px 24px; }
.tl-sum { margin: 0 0 18px; font-size: .92rem; line-height: 1.55; color: $sub; }
h2 { margin: 0 0 6px; font-size: .8rem; font-weight: 700; color: $accent; }
.tl-chapters {
    list-style: none; margin: 0; padding: 0;
    li { display: flex; gap: 12px; padding: 13px 0; border-top: 1px solid $line-soft; }
    li:last-child { border-bottom: 1px solid $line-soft; }
}
.tl-no { width: 1.4em; font-weight: 700; color: $sub-2; font-variant-numeric: tabular-nums; }
.tl-title { font-size: .98rem; line-height: 1.45; }
.tl-soon { margin: 16px 0 0; font-size: .82rem; color: $sub-2; }
.tl-btn {
    min-height: 44px; padding: 0 16px; border: 1px solid $line-2; border-radius: 8px;
    background: $card; color: $brown-ink; font: inherit; font-weight: 700; cursor: pointer;
}
</style>
