<template>
  <main class="yb">
    <!-- 첫 화면: 왼쪽 카피 + 설치 버튼, 오른쪽 홈 화면과 떠 있는 말풍선 -->
    <section class="hero">
      <div class="wrap-wide hero-in">
        <div class="hero-copy" data-reveal>
          <img class="bee" src="/img/bee.png" alt="" width="52" height="52" />
          <h1>감이 아니라,<br /><span>기준으로.</span></h1>
          <p class="lead">내 성향에 맞는 종목과 그 이유를 쉬운 말로.<br />질문 3개면 나만의 기준으로 시작할 수 있어요.</p>
          <InstallButtons />
          <p class="free"><span>기본 기능 무료</span><span>가입 없이 둘러보기</span></p>
        </div>
        <div class="hero-art" data-reveal>
          <img class="hero-shot" src="/img/screen-1.webp" alt="양봉상회 홈 화면: 관심 종목, 오늘 시장, AI 분석 종목" width="900" height="1528" />
          <p class="float f1"><b>오늘 시장</b>시장이 조금 오른 날이에요</p>
          <p class="float f2"><b>내 관심 종목</b>거래량이 평소보다 늘었어요</p>
        </div>
      </div>
    </section>

    <!-- 숫자 띠 -->
    <section class="facts" aria-label="양봉상회 한눈에">
      <div class="wrap-wide facts-in">
        <p v-for="f in FACTS" :key="f.label" class="fact" data-reveal><b>{{ f.value }}</b><span>{{ f.label }}</span></p>
      </div>
    </section>

    <!-- 기능 바로가기: 스크롤하면 위에 붙고, 지금 보는 기능에 밑줄 -->
    <nav class="feature-nav" aria-label="기능 바로가기">
      <div class="wrap-wide">
        <a
          v-for="n in NAV"
          :key="n.id"
          :href="`#${n.id}`"
          :class="{ on: active === n.id }"
          @click.prevent="go(n.id)"
        >{{ n.label }}</a>
      </div>
    </nav>

    <!-- 시작 3단계 -->
    <section id="start" ref="startEl" class="sec center wrap-wide">
      <p class="kick" data-reveal>시작하기</p>
      <h2 data-reveal>1분이면 나만의 기준이 생겨요</h2>
      <p class="desc" data-reveal>복잡한 가입 없이, 질문 몇 개로 바로 시작합니다.</p>
      <ol class="steps">
        <li v-for="(s, i) in STEPS" :key="s.title" class="step" data-reveal>
          <i>{{ i + 1 }}</i>
          <h3>{{ s.title }}</h3>
          <p>{{ s.desc }}</p>
        </li>
      </ol>
    </section>

    <!-- 기능 상세: 글과 화면을 좌우로 번갈아 -->
    <section
      v-for="(f, i) in FEATURES"
      :id="f.id"
      :key="f.id"
      ref="sections"
      class="feature wrap-wide"
      :class="{ rev: i % 2 === 1 }"
    >
      <div class="f-txt" data-reveal>
        <p class="kick">{{ f.label }}</p>
        <h2>{{ f.title[0] }}<br />{{ f.title[1] }}</h2>
        <p class="desc" v-html="f.desc"></p>
        <ul class="points">
          <li v-for="p in f.points" :key="p">{{ p }}</li>
        </ul>
      </div>
      <div class="f-art" data-reveal>
        <img :src="f.img" :alt="f.alt" width="900" height="1528" loading="lazy" decoding="async" />
      </div>
    </section>

    <!-- 배우면서 시작하기 -->
    <section class="sec wrap-wide">
      <div class="learn" data-reveal>
        <div>
          <p class="kick">처음이라도 괜찮아요</p>
          <h2>주식, 배우면서<br />시작하세요</h2>
          <p class="desc">어려운 말은 쉬운 말로 바꾸고, 배운 것은 퀴즈로 확인해요.</p>
        </div>
        <div class="learn-n">
          <p><b>36</b><span>단계 수업</span></p>
          <p><b>36</b><span>문제 퀴즈</span></p>
          <p><b>70</b><span>개 용어</span></p>
        </div>
      </div>
    </section>

    <!-- 자주 묻는 질문 -->
    <section id="faq" class="sec center wrap-wide faq-sec">
      <p class="kick" data-reveal>자주 묻는 질문</p>
      <h2 data-reveal>궁금한 점을 모아 두었어요</h2>
      <div class="faq">
        <div v-for="(q, i) in FAQ" :key="q.q" class="qa-item" :class="{ open: openFaq === i }" data-reveal>
          <button type="button" class="qa" :aria-expanded="openFaq === i ? 'true' : 'false'" @click="openFaq = openFaq === i ? -1 : i">
            <span>{{ q.q }}</span><span class="pm" aria-hidden="true">+</span>
          </button>
          <div class="qa-a"><p>{{ q.a }}</p></div>
        </div>
      </div>
    </section>

    <!-- 마무리: 설치 -->
    <section id="install" class="wrap-wide">
      <div class="closing" data-reveal>
        <img class="bee" src="/img/bee.png" alt="" width="44" height="44" />
        <p class="kick">기본 콘텐츠는 모두 무료</p>
        <h2>오늘 볼 종목,<br />이제 기준으로 고르세요.</h2>
        <InstallButtons center />
      </div>

      <div class="notice" aria-label="투자 유의사항" data-reveal>
        <h2>꼭 알아 두세요</h2>
        <ul>
          <li>양봉상회가 보여 주는 정보는 참고 자료이며 투자 권유가 아닙니다. 투자 판단과 그 결과의 책임은 이용자 본인에게 있습니다.</li>
          <li>주식 투자는 원금 손실이 날 수 있습니다.</li>
          <li>과거 성과는 앞으로의 수익을 보장하지 않습니다.</li>
          <li>화면의 시세는 실제보다 몇 분 늦을 수 있습니다.</li>
        </ul>
      </div>
    </section>

    <!-- 모바일: 화면 아래 고정 설치 버튼 -->
    <a class="sticky-install" href="#install" @click.prevent="go('install')">양봉상회 앱 설치하기</a>
  </main>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';
import InstallButtons from '@/components/InstallButtons.vue';

const FACTS = [
  { value: '3개', label: '질문으로 성향 찾기' },
  { value: '36단계', label: '주식 수업' },
  { value: '70개', label: '쉬운 용어 사전' },
  { value: '0원', label: '기본 기능 이용료' },
];

const STEPS = [
  { title: '질문 3개에 답해요', desc: '떨어질 때 어떻게 할지, 어떤 회사에 눈이 가는지 골라요.' },
  { title: '내 성향을 알려드려요', desc: '안정형, 균형형, 공격형 중 나에게 맞는 기준을 정해요.' },
  { title: '맞는 종목을 담아요', desc: '조건에 맞는 종목과 이유를 보고, 관심 종목으로 담아 둬요.' },
];

// 화면 이미지는 yangbong-store-vue/store-assets/ios-6.9 스토어 스크린샷에서 폰 부분만 잘라 낸 것(public/img/screen-N.webp).
// screen-5(AI 분석)는 스토어 이미지에 없어서, yangbong-store-vue 목업 모드(npm run dev:mock) 종목 상세 'AI 견해' 탭을 찍어 같은 폰 테두리에 합성했다.
// 문구는 실제 화면에 있는 기능만 쓴다. 프리미엄(준비 중)은 출시 전까지 넣지 않는다.
const FEATURES = [
  {
    id: 'market',
    label: '오늘 시장',
    title: ['오늘 시장이 어떤지,', '날씨처럼 한눈에.'],
    desc: '코스피·코스닥·원/달러 흐름을 한 줄 요약으로 보여 드립니다. 관심 종목의 거래량이 평소보다 크게 늘면 바로 알 수 있어요.',
    points: ['시장 분위기를 날씨처럼 한 줄로', '코스피·코스닥·원/달러 오늘 등락', '관심 종목의 큰 변화만 골라서'],
    img: '/img/screen-1.webp',
    alt: '양봉상회 홈 화면: 관심 종목, 오늘 시장, AI 분석 종목',
  },
  {
    id: 'picks',
    label: '주목 종목',
    title: ['고른 종목마다,', '고른 이유까지.'],
    desc: 'AI가 내 조건에 맞는 종목을 고르고, 왜 골랐는지 쉬운 말로 알려 드립니다. 아직 충족하지 못한 조건도 함께 보여 드려요.',
    points: ['주목한 이유 3가지', '아직 아닌 것', '내 조건 충족 개수'],
    img: '/img/screen-2.webp',
    alt: '주목 종목 화면: 종목별 주목한 이유와 아직 아닌 것',
  },
  {
    id: 'ai',
    label: 'AI 분석',
    title: ['궁금한 종목은,', 'AI가 깊이 읽어 드려요.'],
    desc: '종목을 검색하면 AI가 무엇을 하는 회사인지, 실적과 재무는 어떤지, 지금 어떤 테마로 묶이는지, 최근 공시와 뉴스까지 쉬운 말로 정리해 드립니다.',
    points: ['기업개요·재무현황', '현재 테마', '최근 공시·뉴스'],
    img: '/img/screen-5.webp',
    alt: '종목 심층 분석 화면: AI가 정리한 기업개요와 재무현황',
  },
  {
    id: 'training',
    label: '트레이닝',
    title: ['차트를 읽는 법도,', '처음부터 차근차근.'],
    desc: '캔들 한 개 읽는 법부터 시작하는 수업과 퀴즈, 용어 사전으로 차트 보는 눈을 기르세요. 모두 무료입니다.',
    points: ['수업 6개 · 36단계', '퀴즈 36문제', '용어 사전 70개'],
    img: '/img/screen-3.webp',
    alt: '트레이닝 화면: 캔들 읽는 법 수업',
  },
  {
    id: 'settings',
    label: '내 설정',
    title: ['내 성향대로 시작하고,', '내 조건대로 고칩니다.'],
    desc: '안정형·균형형·공격형 중 하나로 시작하세요. 거래량, MACD 같은 보조지표를 켜고 끄고, 수치를 직접 바꿀 수 있습니다.',
    points: ['안정형·균형형·공격형으로 바로 시작', '보조지표를 하나씩 켜고 끄기', '수치를 내 기준에 맞게 조정'],
    img: '/img/screen-4.webp',
    alt: '내 설정 화면: 성향 선택과 보조지표 조절',
  },
];

const NAV = [{ id: 'start', label: '시작하기' }, ...FEATURES.map((f) => ({ id: f.id, label: f.label })), { id: 'faq', label: '자주 묻는 질문' }];

const FAQ = [
  { q: '무료인가요?', a: '네, 기본 기능은 모두 무료예요. 더 깊은 분석을 담은 프리미엄은 준비 중이에요.' },
  { q: '가입해야 쓸 수 있나요?', a: '아니요. 홈, 주목 종목, 트레이닝은 가입 없이 볼 수 있어요. 가입하면 내 성향과 설정을 계정에 저장할 수 있어요.' },
  { q: '종목은 어떻게 골라지나요?', a: '거래량, 이동평균선, 볼린저밴드, MACD 같은 보조지표 조건을 확인해, 내 성향에 맞는 조건을 충족한 종목을 보여 드려요.' },
  { q: '보여 주는 종목을 사면 되나요?', a: '양봉상회는 판단을 돕는 정보와 교육을 제공할 뿐, 투자를 권하거나 매매하지 않아요. 투자 판단과 책임은 본인에게 있어요.' },
  { q: '시세는 실시간인가요?', a: '아니요. 화면의 시세는 실제보다 늦을 수 있어요. 투자 판단 전에는 증권사 시세를 함께 확인하세요.' },
];

const active = ref(NAV[0].id);
const openFaq = ref(-1);
const sections = ref([]);
const startEl = ref(null);
let navIo;
let revealIo;

const go = (id) => {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  history.replaceState(null, '', `#${id}`);
};

onMounted(() => {
  // 화면 위쪽 40% 지점을 지나는 섹션을 '지금 보는 기능'으로 친다
  navIo = new IntersectionObserver(
    (entries) => {
      for (const e of entries) if (e.isIntersecting) active.value = e.target.id;
    },
    { rootMargin: '-40% 0px -55% 0px' },
  );
  [startEl.value, ...sections.value, document.getElementById('faq')].forEach((el) => el && navIo.observe(el));

  // 스크롤 등장: 같은 부모 안에서는 조금씩 늦게. 움직임 줄이기 설정이면 바로 보인다
  const items = document.querySelectorAll('.yb [data-reveal]');
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  if (reduce || !('IntersectionObserver' in window)) {
    items.forEach((el) => el.classList.add('is-in'));
    return;
  }
  items.forEach((el) => {
    const sibs = [...el.parentNode.children].filter((c) => c.hasAttribute('data-reveal'));
    el.style.transitionDelay = `${Math.min(sibs.indexOf(el), 5) * 70}ms`;
  });
  revealIo = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        e.target.classList.add('is-in');
        revealIo.unobserve(e.target);
      }
    },
    { rootMargin: '0px 0px -8% 0px', threshold: 0.12 },
  );
  items.forEach((el) => revealIo.observe(el));
});
onBeforeUnmount(() => {
  navIo?.disconnect();
  revealIo?.disconnect();
});
</script>

<style scoped>
.yb { --honey-100: #fff6e0; --honey-200: #ffefc4; --honey-500: #f8c844; --amber: #b76e00; --honey-ink: #4a2f00; }
.wrap-wide { max-width: 1120px; margin: 0 auto; padding-left: 40px; padding-right: 40px; }

.kick {
  display: inline-block; margin: 0; padding: 6px 10px; border-radius: 6px;
  background: var(--honey-100); color: var(--amber); font-size: 13px; font-weight: 800; line-height: 1.4;
}
.desc { margin: 18px 0 0; color: var(--sub); font-size: 17px; line-height: 1.7; }
.center { text-align: center; }
.center .desc { max-width: 620px; margin-left: auto; margin-right: auto; }

/* 첫 화면 */
.hero { background: var(--panel); overflow: hidden; padding-top: 64px; }
.hero-in { display: grid; grid-template-columns: 1.05fr .95fr; gap: 40px; align-items: end; }
.hero-copy { padding-bottom: 96px; }
.bee { display: block; width: 52px; height: 52px; animation: buzz 3.2s ease-in-out infinite; transform-origin: 50% 60%; }
.hero h1 { margin: 18px 0 0; font-size: 58px; line-height: 1.15; letter-spacing: -0.035em; font-weight: 800; color: var(--panel-ink); }
.hero h1 span { color: var(--amber); }
.lead { margin: 22px 0 32px; color: #5c4630; font-size: 19px; line-height: 1.7; }
.free { display: flex; flex-wrap: wrap; gap: 14px; margin: 16px 0 0; color: #6f5420; font-size: 14px; }
.free span::before { content: '✓'; margin-right: 6px; color: var(--amber); font-weight: 800; }
.hero-art { position: relative; height: 560px; }
.hero-shot { position: absolute; left: 50%; bottom: 0; width: 330px; height: auto; transform: translateX(-50%); }
.float {
  position: absolute; margin: 0; padding: 12px 14px; border-radius: 14px; background: #fff;
  box-shadow: 0 12px 30px rgba(74, 47, 0, .12); color: #191f28; font-size: 14px; line-height: 1.4; white-space: nowrap;
}
.float b { display: block; margin-bottom: 2px; color: var(--amber); font-size: 12px; }
.f1 { left: 0; top: 110px; }
.f2 { right: 0; top: 250px; }
.hero-art.is-in .f1 { animation: bob 5s ease-in-out infinite; }
.hero-art.is-in .f2 { animation: bob 6s ease-in-out .8s infinite; }

/* 숫자 띠 */
.facts { border-bottom: 1px solid var(--line); }
.facts-in { display: grid; grid-template-columns: repeat(4, 1fr); }
.fact { margin: 0; padding: 34px 10px; text-align: center; border-right: 1px solid var(--line); }
.fact:last-child { border-right: 0; }
.fact b { display: block; font-size: 30px; letter-spacing: -0.03em; line-height: 1.3; }
.fact span { display: block; margin-top: 4px; color: var(--sub); font-size: 14px; }

/* 기능 바로가기 */
.feature-nav {
  position: sticky; top: 0; z-index: 5;
  background: color-mix(in srgb, var(--bg) 92%, transparent);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
}
.feature-nav .wrap-wide { display: flex; gap: 26px; overflow-x: auto; scrollbar-width: none; }
.feature-nav .wrap-wide::-webkit-scrollbar { display: none; }
.feature-nav a {
  flex: none; padding: 14px 0 12px; border-bottom: 2px solid transparent;
  color: var(--sub); font-size: 15px; text-decoration: none; white-space: nowrap;
}
.feature-nav a.on { color: var(--ink); font-weight: 600; border-bottom-color: var(--brand); }

/* 공통 섹션 */
.sec { padding-top: 120px; padding-bottom: 120px; scroll-margin-top: 48px; }
.sec h2, .f-txt h2 { margin: 16px 0 0; font-size: 42px; line-height: 1.25; letter-spacing: -0.03em; font-weight: 800; }

/* 시작 3단계 */
.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 56px 0 0; padding: 0; list-style: none; }
.step {
  position: relative; padding: 32px 28px; border-radius: 18px; text-align: left;
  background: var(--panel); border: 1px solid var(--honey-200); color: var(--panel-ink);
  transition: transform .3s, box-shadow .3s;
}
.step:hover { transform: translateY(-4px); box-shadow: 0 14px 30px rgba(74, 47, 0, .08); }
.step i {
  display: inline-flex; width: 34px; height: 34px; align-items: center; justify-content: center;
  border-radius: 10px; background: var(--honey-500); color: var(--honey-ink); font-style: normal; font-weight: 800;
}
.step h3 { margin: 18px 0 0; font-size: 21px; letter-spacing: -0.02em; }
.step p { margin: 8px 0 0; color: #6f5420; font-size: 15px; line-height: 1.6; }

/* 기능 상세 */
.feature { display: grid; grid-template-columns: 1fr 1fr; gap: 64px; align-items: center; padding-top: 72px; padding-bottom: 72px; scroll-margin-top: 48px; }
.feature.rev .f-txt { order: 2; }
.f-txt .desc { font-size: 17px; }
.points { margin: 26px 0 0; padding: 0; list-style: none; }
.points li { display: flex; gap: 10px; padding: 12px 0; border-top: 1px solid var(--line); font-size: 16px; line-height: 1.5; }
.points li::before {
  content: '✓'; flex: none; display: inline-flex; width: 20px; height: 20px; align-items: center; justify-content: center;
  border-radius: 50%; background: var(--honey-100); color: var(--amber); font-size: 12px; font-weight: 800;
}
.f-art {
  height: 540px; display: flex; justify-content: center; align-items: flex-start; overflow: hidden;
  padding-top: 48px; border-radius: 24px; background: var(--panel);
}
.f-art img { display: block; width: 330px; height: auto; }

/* 배우면서 시작하기 */
.learn {
  display: grid; grid-template-columns: 1fr 1fr; gap: 48px; align-items: center;
  padding: 64px; border-radius: 28px; background: var(--honey-100); color: var(--panel-ink);
}
.learn h2 { font-size: 36px; }
.learn .desc { color: #6f5420; }
.learn-n { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.learn-n p { margin: 0; padding: 22px 18px; border-radius: 16px; background: #fff; color: #191f28; }
.learn-n b { display: block; font-size: 30px; letter-spacing: -0.03em; line-height: 1.3; }
.learn-n span { display: block; margin-top: 4px; color: #6b7684; font-size: 14px; }

/* 자주 묻는 질문 */
.faq-sec { padding-top: 20px; }
.faq { max-width: 780px; margin: 48px auto 0; text-align: left; }
.qa {
  width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 16px;
  padding: 24px 4px; border: 0; border-bottom: 1px solid var(--line); background: transparent;
  font: inherit; font-size: 17px; font-weight: 600; color: inherit; text-align: left; cursor: pointer;
}
.qa .pm { color: var(--muted); font-size: 22px; transition: transform .25s; }
.qa[aria-expanded='true'] .pm { transform: rotate(45deg); }
.qa-a { display: grid; grid-template-rows: 0fr; transition: grid-template-rows .3s ease; }
.qa-a > p { overflow: hidden; margin: 0; color: var(--sub); font-size: 15.5px; line-height: 1.7; }
.qa-item.open .qa-a { grid-template-rows: 1fr; }
.qa-item.open .qa-a > p { padding: 16px 4px 22px; }

/* 마무리 */
#install { scroll-margin-top: 48px; padding-bottom: 80px; }
.closing { padding: 72px 40px; border-radius: 28px; background: var(--panel); text-align: center; color: var(--panel-ink); }
.closing .bee { margin: 0 auto 16px; width: 44px; height: 44px; }
.closing h2 { margin: 16px 0 28px; font-size: 40px; line-height: 1.3; letter-spacing: -0.03em; font-weight: 800; }
.notice { margin-top: 48px; padding: 28px 30px; border-radius: 16px; background: var(--head); }
.notice h2 { margin: 0 0 8px; font-size: 15px; }
.notice ul { margin: 0; padding-left: 18px; color: var(--sub); font-size: 14px; }
.notice li { margin: 3px 0; }

.sticky-install { display: none; }

/* 움직임 */
[data-reveal] { opacity: 0; transform: translateY(18px); transition: opacity .7s cubic-bezier(.2, .7, .2, 1), transform .7s cubic-bezier(.2, .7, .2, 1); }
[data-reveal].is-in { opacity: 1; transform: none; }
.step[data-reveal].is-in:hover { transform: translateY(-4px); }
@keyframes bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-7px); } }
@keyframes buzz { 0%, 100% { transform: rotate(0); } 25% { transform: rotate(-8deg) translateY(-2px); } 75% { transform: rotate(6deg); } }
@media (prefers-reduced-motion: reduce) {
  [data-reveal] { opacity: 1; transform: none; transition: none; }
  .bee, .float { animation: none !important; }
  .step, .qa-a, .qa .pm { transition: none; }
}

/* 태블릿 */
@media (max-width: 1024px) {
  .wrap-wide { padding-left: 32px; padding-right: 32px; }
  .hero h1 { font-size: 46px; }
  .hero-art { height: 500px; }
  .hero-shot { width: 290px; }
  .f1 { left: -10px; } .f2 { right: -10px; }
  .feature { gap: 36px; }
  .f-art { height: 470px; }
  .f-art img { width: 280px; }
  .learn { grid-template-columns: 1fr; padding: 48px; }
}

/* 모바일 */
@media (max-width: 720px) {
  .wrap-wide { padding-left: 24px; padding-right: 24px; }
  .hero { padding-top: 44px; }
  .hero-in { grid-template-columns: 1fr; gap: 12px; }
  .hero-copy { padding-bottom: 20px; }
  .hero h1 { font-size: 38px; }
  .lead { margin: 18px 0 28px; font-size: 16.5px; }
  .hero-art { height: 440px; }
  .hero-shot { width: 260px; }
  .float { padding: 10px 12px; font-size: 13px; }
  .f1 { left: 0; top: 40px; } .f2 { right: 0; top: 170px; }
  .facts-in { grid-template-columns: 1fr 1fr; }
  .fact { padding: 26px 8px; }
  .fact:nth-child(2) { border-right: 0; }
  .fact:nth-child(-n + 2) { border-bottom: 1px solid var(--line); }
  .fact b { font-size: 24px; }
  .sec { padding-top: 96px; padding-bottom: 96px; }
  .sec h2, .f-txt h2 { font-size: 30px; }
  .desc, .f-txt .desc { font-size: 16px; }
  .steps { grid-template-columns: 1fr; gap: 16px; margin-top: 40px; }
  .feature, .feature.rev { grid-template-columns: 1fr; gap: 32px; padding-top: 56px; padding-bottom: 56px; }
  .feature.rev .f-txt { order: 0; }
  .f-art { height: 430px; padding-top: 36px; border-radius: 20px; }
  .f-art img { width: 250px; }
  .learn { padding: 36px 24px; border-radius: 22px; gap: 28px; }
  .learn h2 { font-size: 28px; }
  .learn-n { gap: 8px; }
  .learn-n p { padding: 16px 10px; }
  .learn-n b { font-size: 22px; }
  .learn-n span { font-size: 12.5px; }
  .qa { padding: 24px 4px; font-size: 16px; }
  .closing { padding: 44px 24px; border-radius: 22px; }
  .closing h2 { font-size: 28px; }
  .notice { padding: 24px 20px; }
  #install { padding-bottom: 96px; }
  .sticky-install {
    display: flex; align-items: center; justify-content: center; position: fixed; left: 24px; right: 24px; bottom: 16px; z-index: 20;
    height: 52px; border-radius: 12px; background: var(--brand); color: #fff8e1; font-weight: 700; font-size: 16px; text-decoration: none;
    box-shadow: 0 10px 24px rgba(58, 36, 20, .2);
  }
}
</style>
