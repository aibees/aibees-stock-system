<template>
    <div id="stock-dashboard">
        <BrandHeader title="주식분석" />

        <main class="sd-main">
            <p class="sd-lead">내 성향에 맞는 회사를 고르고, 종목을 분석하고, 차트를 확인해 보세요.</p>
            <ul class="sd-list">
                <li v-for="t in tiles" :key="t.path">
                    <button type="button" class="sd-tile" @click="router.push(t.path)">
                        <span class="sd-text">
                            <span class="sd-name">{{ t.name }}</span>
                            <span class="sd-desc">{{ t.desc }}</span>
                        </span>
                        <svg class="chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="m9 6 6 6-6 6"></path></svg>
                    </button>
                </li>
            </ul>
            <p v-if="!tiles.length" class="sd-empty">이용할 수 있는 메뉴가 없어요.</p>
        </main>
    </div>
</template>

<script setup>
/**
 * 주식분석 허브. 하단 탭 하나("주식분석")로 묶고, 하위 화면은 여기서 들어간다(2026-11-15).
 * 권한이 없는 화면은 서버가 준 접근 경로(access.paths)에 없으므로 나오지 않는다.
 */
import { assUserSession } from '@scripts/stores/user-stores.js';
import { ensureAccess } from '@scripts/useAccess.js';

const router = useRouter();
const userSession = assUserSession();

const ALL = [
    { path: '/stock/buy-target', name: '매수추천', desc: '내 성향에 맞는 회사를 순서대로 보여 드려요' },
    { path: '/stock/info',       name: 'AI 분석',  desc: '종목을 하나 골라 사업·재무·뉴스를 분석해 드려요' },
    { path: '/stock/chart',      name: '차트 확인', desc: '일·주·월봉과 이동평균선으로 차트를 살펴보세요' },
];
const tiles = computed(() => ALL.filter(t => userSession.access.paths.includes(t.path)));

onMounted(() => ensureAccess());
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#stock-dashboard {
    min-height: 100vh;
    background: $card;
    color: $ink;
    text-align: left;
    font-family: $font-body;
}
.sd-main { max-width: 720px; margin: 0 auto; padding: 14px 0 24px; }
.sd-lead { margin: 0 16px 8px; font-size: 14px; line-height: 1.5; color: $sub; }
.sd-list { list-style: none; margin: 0; padding: 0; border-top: 1px solid $line-soft; }
.sd-list li { border-bottom: 1px solid $line-soft; }
.sd-tile {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 68px;
    padding: 14px 16px;
    box-sizing: border-box;
    border: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
    @media (hover: hover) { &:hover { background: #FFFDF3; } }
    &:active { background: $bar; }
}
.sd-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.sd-name { font-size: 17px; font-weight: 700; }
.sd-desc { font-size: 13px; line-height: 1.4; color: $sub; }
.chev { color: $sub-2; flex-shrink: 0; }
.sd-empty { margin: 24px 16px; font-size: 14px; color: $sub; text-align: center; }
</style>
