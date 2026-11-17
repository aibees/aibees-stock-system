<template>
    <header class="brand-header" data-ad-anchor>
        <div class="bh-row">
            <button v-if="back" type="button" class="bh-back" aria-label="뒤로" @click="goBack">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 5-7 7 7 7"></path></svg>
            </button>
            <h1 class="bh-title">{{ title }}</h1>
            <div class="bh-right"><slot /></div>
        </div>
    </header>
</template>

<script setup>
/**
 * 양봉상회 공통 화면 헤더(v2). 홈/내 자산/트레이드 대시보드와 같은 모양.
 *  - 모바일: 상태바(세이프 에어리어) 아래에 sticky. 상태바 영역 자체는 App.vue 의 고정 덮개가 가린다.
 *  - 데스크톱: 상단 내비(Lnb)가 있으니 흐름에 둔다.
 *  - back 이 있으면 ‹ 버튼으로 그 경로에 돌아간다(예: 트레이드 하위 화면 → /trade).
 *  - 오른쪽 슬롯에 새로고침 같은 버튼을 넣을 수 있다.
 */
const props = defineProps({
    title: { type: String, default: '' },
    back: { type: String, default: '' },
});

const router = useRouter();
const goBack = () => router.push({ path: props.back });
</script>

<style scoped lang="scss">
// 2026-11-17 화이트 톤 개편: 흰 바탕, 구분선 없이 큰 제목(스크롤해도 같은 흰 바탕이라 선이 필요 없다)
.brand-header {
    position: sticky;
    top: env(safe-area-inset-top, 0px);
    z-index: 50;
    background: #FFFFFF;
    padding: 0 8px 0 12px;
    text-align: left;
    font-family: 'Pretendard', -apple-system, 'Apple SD Gothic Neo', sans-serif;

    @media (min-width: 640px) { position: static; }
}

.bh-row { display: flex; align-items: center; min-height: 56px; gap: 2px; }

.bh-back {
    width: 44px;
    height: 44px;
    border: 0;
    background: transparent;
    color: #191F28;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}

.bh-title {
    flex: 1;
    margin: 0;
    padding-left: 8px;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.6px;
    color: #191F28;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.bh-back + .bh-title { padding-left: 0; }

.bh-right { display: flex; align-items: center; }
</style>
