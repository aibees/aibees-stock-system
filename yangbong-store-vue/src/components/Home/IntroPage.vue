<template>
    <div id="intro-page">
        <header class="top">
            <span class="brand"><img src="/favicon.svg" alt="" />양봉상회</span>
            <button type="button" class="link" @click="skip">둘러보기</button>
        </header>
        <main class="hero">
            <img class="bee" src="/img/emoji/bee.png" alt="" />
            <div class="copy">
                <h1>주식의 첫걸음부터<br />전문적인 분석까지</h1>
                <p>질문 3개면 시작할 수 있어요</p>
                <button type="button" class="cta" @click="start">내 종목 찾기</button>
            </div>
        </main>
    </div>
</template>

<script setup>
/** 첫 1분의 시작: 한 장 소개 → 질문 3개 → 내 조건에 맞는 종목. */
import { ONBOARDING_PATH } from '@scripts/authPaths.js';
import { markIntroSeen } from '@scripts/introState.js';
import { usePersonaStore } from '@scripts/stores/persona-store.js';

const router = useRouter();
const persona = usePersonaStore();
const skip = () => {
    markIntroSeen();
    if (!persona.decided) persona.skip();
    router.replace('/home');
};
const start = () => { markIntroSeen(); router.push(ONBOARDING_PATH); };
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

$intro-bg: #FFF5D9;
$intro-ink: #3F2A00;
$intro-sub: #6F5420;
#intro-page { min-height: 100vh; min-height: 100dvh; display: flex; flex-direction: column; background: $intro-bg; color: $intro-ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; -webkit-font-smoothing: antialiased; }
button { border: 0; background: transparent; color: inherit; font: inherit; letter-spacing: inherit; cursor: pointer; }
.top { flex: none; height: 56px; padding: 0 24px; display: flex; align-items: center; justify-content: space-between; }
.brand { display: inline-flex; align-items: center; gap: 7px; font-size: 16px; font-weight: 700; img { width: 24px; height: 24px; } }
.link { min-height: 40px; color: $intro-sub; font-size: 14px; }
.hero { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 30px; padding: 0 24px calc(24px + env(safe-area-inset-bottom, 0px)); text-align: center; }
.bee { width: 88px; height: 88px; }
.copy { width: 100%; flex: 0; display: contents; }
h1 { margin: 0; font-size: 27px; line-height: 1.32; letter-spacing: -0.8px; word-break: keep-all; }
p { margin: -16px 0 0; font-size: 14px; color: $intro-sub; }
.cta { position: absolute; left: 24px; right: 24px; bottom: calc(24px + env(safe-area-inset-bottom, 0px)); height: 54px; border-radius: $radius; background: #5A3C08; color: #fff; font-size: 17px; font-weight: 700; }
@media (min-width: 700px) {
    .top { height: 72px; padding: 0 40px; }
    .hero { flex-direction: row-reverse; gap: 72px; padding: 0 56px 72px; text-align: left; }
    .copy { display: block; flex: none; width: auto; }
    .bee { width: 128px; height: 128px; }
    h1 { font-size: 40px; letter-spacing: -1px; }
    p { margin: 12px 0 0; font-size: 16px; }
    .cta { position: static; display: block; width: 260px; margin-top: 28px; }
}
</style>

<style>
body:has(#intro-page)::before { background: #FFF5D9; }
</style>
