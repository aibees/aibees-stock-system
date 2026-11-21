<template>
    <div v-if="stockNotice.show" class="sn-dim" @click.self="close">
        <section class="sn-sheet" role="dialog" aria-modal="true" aria-labelledby="sn-title">
            <h2 id="sn-title">주식분석을 시작할까요?</h2>
            <p class="sn-lead">시작하기 전에 아래 유의사항을 꼭 읽어 주세요.</p>

            <ol class="sn-list" tabindex="0">
                <li v-for="(it, i) in STOCK_NOTICE_ITEMS" :key="i">
                    <b>{{ it.title }}</b>
                    <span>{{ it.body }}</span>
                </li>
            </ol>

            <label class="sn-check">
                <input v-model="checked" type="checkbox" />
                <span>위 유의사항을 읽고 이해했습니다</span>
            </label>

            <button type="button" class="sn-ok" :disabled="!checked" @click="confirm">확인하고 시작하기</button>
            <button type="button" class="sn-later" @click="close">다음에 할게요</button>
        </section>
    </div>
</template>

<script setup>
/**
 * 주식분석 유의사항 팝업 — 내비에서 주식분석을 처음 누를 때(scripts/stockNotice.js 의 requireStockNotice).
 * "이해했습니다"를 체크해야 확인할 수 있고, 확인하면 동의를 기록하고 누른 경로로 간다.
 */
import { stockNotice, STOCK_NOTICE_ITEMS, markStockNoticeAgreed } from '@scripts/stockNotice.js';

const router = useRouter();
const checked = ref(false);

watch(() => stockNotice.show, (v) => {
    if (v) checked.value = false;
    // 팝업이 떠 있는 동안 뒤 화면이 스크롤되지 않게
    document.documentElement.style.overflow = v ? 'hidden' : '';
});

const close = () => { stockNotice.show = false; };
const confirm = () => {
    if (!checked.value) return;
    markStockNoticeAgreed();
    stockNotice.show = false;
    if (stockNotice.path) router.push({ path: stockNotice.path });
};
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

$btn: #5A3C08;

.sn-dim {
    // app-shell 의 직계 자식이라 탭바 여백(padding-bottom)이 붙는다 — 팝업은 탭바까지 덮으므로 없앤다
    position: fixed; inset: 0; z-index: 1300; padding: 0 !important;
    display: flex; align-items: flex-end; justify-content: center;
    background: rgba(25, 31, 40, .42);
    font-family: $font-body; color: $ink; text-align: left; letter-spacing: -0.2px;
}
.sn-sheet {
    width: 100%; max-width: 480px; max-height: calc(100dvh - 24px); box-sizing: border-box;
    display: flex; flex-direction: column;
    padding: 22px 22px calc(16px + env(safe-area-inset-bottom, 0px));
    border-radius: 16px 16px 0 0; background: $card;
}
h2 { margin: 0; font-size: 21px; line-height: 1.35; letter-spacing: -0.5px; }
.sn-lead { margin: 6px 0 0; font-size: 14px; line-height: 1.5; color: $sub-ink; }

.sn-list {
    flex: 1 1 auto; min-height: 0; overflow-y: auto; -webkit-overflow-scrolling: touch;
    margin: 14px 0 0; padding: 4px 14px 4px 32px; border-radius: $radius; background: $bg;
    li { padding: 10px 0; font-size: 13px; line-height: 1.55; color: $sub-ink; word-break: keep-all; }
    li + li { border-top: 1px solid $line; }
    li::marker { color: $amber-700; font-weight: 700; }
    b { display: block; margin-bottom: 2px; font-size: 14px; font-weight: 700; color: $ink; }
}

.sn-check {
    display: flex; align-items: center; gap: 10px; margin: 14px 0 12px; min-height: 44px;
    font-size: 15px; font-weight: 600; cursor: pointer;
    input { width: 22px; height: 22px; flex: none; margin: 0; accent-color: $btn; }
}
.sn-ok {
    width: 100%; height: 54px; flex: none; border: 0; border-radius: $radius; background: $btn; color: #fff;
    font: inherit; font-size: 17px; font-weight: 700; cursor: pointer;
    &:disabled { background: $band; color: $sub; cursor: default; }
}
.sn-later {
    width: 100%; height: 40px; flex: none; margin-top: 4px; border: 0; background: transparent;
    color: $sub; font: inherit; font-size: 14px; cursor: pointer;
}

@media (min-width: 700px) {
    .sn-dim { align-items: center; }
    .sn-sheet { border-radius: 16px; padding-bottom: 18px; }
}
</style>
