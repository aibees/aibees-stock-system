<template>
    <div id="intro-page">
        <!-- 모바일·패드: 넘겨 보는 4장 -->
        <section class="carousel" aria-label="양봉상회 소개">
            <header class="top">
                <span class="brand"><img src="/favicon.svg" alt="" />양봉상회</span>
                <button v-if="!isLast" type="button" class="link" @click="skip">건너뛰기</button>
            </header>

            <div ref="track" class="track" tabindex="0" @scroll.passive="onScroll">
                <article v-for="(s, i) in slides" :key="s.key" class="slide" :aria-label="`${i + 1} / ${slides.length}`">
                    <div class="art" aria-hidden="true">
                        <div v-if="s.key === 'start'" class="hero">
                            <img class="bee" src="/img/emoji/bee.png" alt="" />
                            <img class="honey" src="/img/emoji/honey.png" alt="" />
                            <img class="chart" src="/img/emoji/chart.png" alt="" />
                        </div>
                        <div v-else-if="s.key === 'ai'" class="ai-card">
                            <small>AI 분석</small>
                            <p><b>예시 종목</b><span>+3.12%</span></p>
                            <em><i>✓</i>거래량이 전날보다 3.2배 늘었어요</em>
                        </div>
                        <div v-else-if="s.key === 'learn'" class="learn">
                            <span class="wide"><img src="/img/emoji/books.png" alt="" />수업 듣기</span>
                            <span><img src="/img/emoji/target.png" alt="" />퀴즈</span>
                            <span><img src="/img/emoji/open-book.png" alt="" />용어 사전</span>
                        </div>
                        <div v-else class="types">
                            <span>안정형</span><span class="on">균형형</span><span>공격형</span>
                        </div>
                    </div>
                    <h1>{{ s.lines[0] }}<br />{{ s.lines[1] }}</h1>
                </article>
            </div>

            <footer class="foot">
                <p v-if="isLast" class="note">{{ NOTICE }}</p>
                <div class="dots">
                    <button v-for="(s, i) in slides" :key="s.key" type="button" :class="{ on: i === index }"
                        :aria-label="`${i + 1}번째 소개 보기`" :aria-current="i === index ? 'true' : undefined" @click="goTo(i)"></button>
                </div>
                <button type="button" class="cta" @click="isLast ? start() : goTo(index + 1)">{{ isLast ? '성향 알아보기' : '다음' }}</button>
                <button v-if="isLast" type="button" class="link login" @click="login">이미 계정이 있어요 · 로그인</button>
            </footer>
        </section>

        <!-- 넓은 화면: 한 화면 소개 -->
        <section class="web" aria-label="양봉상회 소개">
            <header class="web-nav">
                <span class="brand"><img src="/favicon.svg" alt="" />양봉상회</span>
                <button type="button" class="link" @click="skip">둘러보기</button>
            </header>
            <div class="web-hero">
                <div>
                    <h1>{{ slides[0].lines[0] }}<br />{{ slides[0].lines[1] }}</h1>
                    <button type="button" class="cta" @click="start">시작하기</button>
                    <button type="button" class="link login" @click="login">이미 계정이 있어요 · 로그인</button>
                </div>
                <img src="/img/emoji/bee.png" alt="" />
            </div>
            <ul class="web-features">
                <li><img src="/img/emoji/chart.png" alt="" />AI와 함께 종목 분석</li>
                <li><img src="/img/emoji/books.png" alt="" />수업과 퀴즈</li>
                <li><img src="/img/emoji/open-book.png" alt="" />용어 사전</li>
            </ul>
            <p class="note">{{ NOTICE }}</p>
        </section>
    </div>
</template>

<script setup>
/**
 * 앱 소개. 앱을 처음 열면 홈 앞에 한 번 보여 주고, 웹은 홈의 "처음이세요?"에서 연다.
 * 소개 → 성향 질문 → 홈 순서. 건너뛰면 기본 성향으로 바로 홈에 간다(이미 정한 성향은 유지).
 */
import { ONBOARDING_PATH } from '@scripts/authPaths.js';
import { markIntroSeen } from '@scripts/introState.js';
import { usePersonaStore } from '@scripts/stores/persona-store.js';

const NOTICE = '투자 판단과 책임은 본인에게 있으며, 원금 손실이 날 수 있습니다.';
const slides = [
    { key: 'start', lines: ['주식의 첫걸음부터', '전문적인 분석까지'] },
    { key: 'ai', lines: ['AI와 함께', '종목을 분석해요'] },
    { key: 'learn', lines: ['배우고, 풀고,', '찾아보세요'] },
    { key: 'persona', lines: ['내 성향을 알려주면', '더 잘 맞춰드려요'] },
];

const router = useRouter();
const persona = usePersonaStore();
const track = ref(null);
const index = ref(0);
const isLast = computed(() => index.value === slides.length - 1);

const onScroll = () => {
    const el = track.value;
    if (el?.clientWidth) index.value = Math.round(el.scrollLeft / el.clientWidth);
};
const goTo = (i) => {
    const el = track.value;
    if (!el) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    el.scrollTo({ left: el.clientWidth * i, behavior: reduce ? 'auto' : 'smooth' });
    index.value = i;
};
const skip = () => {
    markIntroSeen();
    if (!persona.decided) persona.skip();
    router.replace('/home');
};
const start = () => { markIntroSeen(); router.push(ONBOARDING_PATH); };
const login = () => { markIntroSeen(); router.push('/login'); };
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

$intro-bg: #FFF5D9;
$intro-ink: #3F2A00;
$intro-sub: #6F5420;
$intro-btn: #5A3C08;

#intro-page { min-height: 100vh; min-height: 100dvh; background: $intro-bg; color: $intro-ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; -webkit-font-smoothing: antialiased; }
button { border: 0; background: transparent; color: inherit; font: inherit; letter-spacing: inherit; cursor: pointer; -webkit-tap-highlight-color: transparent; }
h1 { margin: 0; font-size: 26px; line-height: 1.32; letter-spacing: -0.8px; word-break: keep-all; }
.brand { display: inline-flex; align-items: center; gap: 7px; font-size: 16px; font-weight: 700; img { width: 24px; height: 24px; } }
.link { min-height: 40px; color: $intro-sub; font-size: 14px; }
.cta { width: 100%; height: 54px; border-radius: $radius; background: $intro-btn; color: #fff; font-size: 17px; font-weight: 700; }
.note { margin: 0 0 12px; font-size: 12px; line-height: 1.5; color: $intro-sub; word-break: keep-all; }

.carousel { height: 100vh; height: 100dvh; display: flex; flex-direction: column; }
.top { flex: none; height: 56px; padding: 0 24px; display: flex; align-items: center; justify-content: space-between; }
.track { flex: 1; min-height: 0; display: flex; overflow-x: auto; scroll-snap-type: x mandatory; scrollbar-width: none; outline: 0; &::-webkit-scrollbar { display: none; } }
.slide { flex: 0 0 100%; min-width: 0; padding: 0 24px; box-sizing: border-box; scroll-snap-align: start; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 28px; text-align: center; }
.art { width: 100%; height: min(300px, 40vh); display: flex; align-items: center; justify-content: center; }
.hero { position: relative; width: 210px; height: 170px; img { position: absolute; } .bee { left: 61px; top: 41px; width: 88px; height: 88px; } .honey { left: 0; top: 0; width: 36px; height: 36px; } .chart { right: 0; bottom: 0; width: 36px; height: 36px; } }
.ai-card { width: min(100%, 270px); padding: 14px; box-sizing: border-box; border-radius: $radius; background: rgba(255, 255, 255, .78); text-align: left;
    small { font-size: 12px; font-weight: 700; color: $amber-700; }
    p { margin: 8px 0 10px; display: flex; align-items: center; justify-content: space-between; }
    b { font-size: 15px; }
    span { padding: 4px 6px; border-radius: $radius-sm; background: $up-bg; color: $up; font-size: 12px; font-weight: 700; }
    em { display: flex; align-items: center; gap: 6px; padding: 8px; border-radius: 8px; background: $honey-strip; font-size: 12px; font-style: normal; }
    i { flex: none; width: 15px; height: 15px; border-radius: 8px; background: $honey-300; font-size: 9px; font-style: normal; display: inline-flex; align-items: center; justify-content: center; }
}
.learn { width: min(100%, 250px); display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
    span { padding: 12px; border-radius: $radius; background: rgba(255, 255, 255, .78); font-size: 14px; font-weight: 700; text-align: left; }
    img { display: block; width: 32px; height: 32px; margin-bottom: 8px; }
    .wide { grid-column: 1 / -1; display: flex; align-items: center; gap: 10px; font-size: 16px; img { width: 38px; height: 38px; margin: 0; } }
}
.types { width: min(100%, 250px); display: flex; flex-direction: column; gap: 8px;
    span { height: 50px; border-radius: $radius; background: rgba(255, 255, 255, .72); font-size: 15px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
    .on { background: #fff; box-shadow: inset 0 0 0 1.5px $intro-btn; }
}
.foot { flex: none; padding: 8px 24px calc(20px + env(safe-area-inset-bottom, 0px)); text-align: center; }
.dots { display: flex; justify-content: center; gap: 2px; margin-bottom: 10px;
    button { width: 18px; height: 24px; padding: 0; display: flex; align-items: center; justify-content: center;
        &::before { content: ''; width: 6px; height: 6px; border-radius: 3px; background: rgba(74, 47, 0, .18); }
        &.on { width: 24px; &::before { width: 18px; background: $intro-btn; } }
    }
}
.login { display: block; width: 100%; margin-top: 4px; }
.web { display: none; }

/* 패드: 그림과 문구를 나란히 */
@media (min-width: 700px) {
    .top { padding: 0 40px; height: 68px; }
    .top { flex: none; }
    .track { flex: none; height: 360px; margin-top: auto; }
    .slide { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; padding: 0 56px; text-align: left; }
    h1 { font-size: 34px; }
    .art { height: 320px; }
    .hero { transform: scale(1.2); }
    .ai-card, .learn, .types { transform: scale(1.12); }
    .foot { position: relative; width: 50%; margin: -82px 0 auto auto; padding: 0 56px env(safe-area-inset-bottom, 0px) 20px; box-sizing: border-box; text-align: left; }
    .dots { justify-content: flex-start; }
    .cta { max-width: 300px; display: block; }
    .login { max-width: 300px; text-align: center; }
}

/* 넓은 화면: 넘기지 않고 한 화면 */
@media (min-width: 1024px) {
    .carousel { display: none; }
    .web { display: flex; flex-direction: column; width: min(100%, 1120px); min-height: 100vh; margin: 0 auto; padding: 0 48px 32px; box-sizing: border-box; }
    .web-nav { height: 76px; display: flex; align-items: center; justify-content: space-between; }
    .web-hero { flex: 1; display: grid; grid-template-columns: 1fr 260px; align-items: center; gap: 48px; h1 { font-size: 48px; letter-spacing: -1.2px; } > img { width: 128px; height: 128px; justify-self: center; } }
    .web-hero .cta { display: block; width: 240px; margin-top: 32px; }
    .web-hero .login { width: 240px; }
    .web-features { list-style: none; margin: 0; padding: 24px 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; font-size: 16px; font-weight: 700; li { display: flex; align-items: center; gap: 10px; } img { width: 32px; height: 32px; } }
    .note { margin: 0; }
}
</style>

<style>
/* 소개 화면에서는 노치 영역도 같은 배경색으로 */
body:has(#intro-page)::before { background: #FFF5D9; }
</style>
