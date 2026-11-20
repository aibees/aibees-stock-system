<template>
  <main>
    <!-- 첫 화면: 왼쪽 정렬 큰 두 줄 제목(둘째 줄은 흐린 색) -->
    <section class="hero wrap-wide">
      <p class="eyebrow">양봉상회</p>
      <h1>
        감이 아니라, 기준으로.
        <span>내 성향에 맞는 종목을 한곳에서.</span>
      </h1>
      <p class="lead">주식을 잘 몰라도 괜찮아요. <br/>내 성향으로 시작 조건을 정하고, <br/>조건에 맞는 종목과 그 이유를 쉬운 말로 확인하세요.</p>
      <InstallButtons />
    </section>

    <!-- 기능 바로가기: 스크롤하면 위에 붙고, 지금 보는 기능에 밑줄 -->
    <nav class="feature-nav" aria-label="기능 바로가기">
      <div class="wrap-wide">
        <a
          v-for="f in FEATURES"
          :key="f.id"
          :href="`#${f.id}`"
          :class="{ on: active === f.id }"
          @click.prevent="go(f.id)"
        >{{ f.label }}</a>
      </div>
    </nav>

    <section
      v-for="(f, i) in FEATURES"
      :id="f.id"
      :key="f.id"
      ref="sections"
      class="feature wrap-wide"
    >
      <p class="num"><span>{{ String(i + 1).padStart(2, '0') }}</span>{{ f.label }}</p>
      <h2>{{ f.title[0] }}<br />{{ f.title[1] }}</h2>
      <p class="desc" v-html="f.desc"></p>
      <ul v-if="f.points" class="points">
        <li v-for="p in f.points" :key="p">{{ p }}</li>
      </ul>
      <div class="shot">
        <img :src="f.img" :alt="f.alt" width="900" height="1528" loading="lazy" decoding="async" />
      </div>
    </section>

    <!-- 마무리 -->
    <section id="install" class="closing">
      <div class="wrap-wide">
        <p class="eyebrow">기본 콘텐츠는 모두 무료</p>
        <h2>오늘 볼 종목,<br />이제 기준으로 고르세요.</h2>
        <InstallButtons center />
      </div>
    </section>

    <section class="notice wrap-wide" aria-label="투자 유의사항">
      <h2>꼭 알아 두세요</h2>
      <ul>
        <li>양봉상회가 보여 주는 정보는 참고 자료이며 투자 권유가 아닙니다. 투자 판단과 그 결과의 책임은 이용자 본인에게 있습니다.</li>
        <li>주식 투자는 원금 손실이 날 수 있습니다.</li>
        <li>과거 성과는 앞으로의 수익을 보장하지 않습니다.</li>
        <li>화면의 시세는 실제보다 몇 분 늦을 수 있습니다.</li>
      </ul>
    </section>
  </main>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';
import InstallButtons from '@/components/InstallButtons.vue';

// 화면 이미지는 yangbong-store-vue/store-assets/ios-6.9 스토어 스크린샷에서 폰 부분만 잘라 낸 것(public/img/screen-N.webp).
// screen-5(AI 분석)는 스토어 이미지에 없어서, yangbong-store-vue 목업 모드(npm run dev:mock) 종목 상세 'AI 견해' 탭을 찍어 같은 폰 테두리에 합성했다.
// 문구는 실제 화면에 있는 기능만 쓴다. 프리미엄(준비 중)은 출시 전까지 넣지 않는다.
const FEATURES = [
  {
    id: 'market',
    label: '오늘 시장',
    title: ['오늘 시장이 어떤지,', '날씨처럼 한눈에.'],
    desc: '코스피·코스닥·원/달러 흐름을 한 줄 요약으로 보여 드립니다. 관심 종목의 거래량이 평소보다 크게 늘면 바로 알 수 있어요.',
    img: '/img/screen-1.webp',
    alt: '양봉상회 홈 화면: 관심 종목, 오늘 시장, AI 분석 종목',
  },
  {
    id: 'picks',
    label: '주목 종목',
    title: ['고른 종목마다,', '고른 이유까지.'],
    desc: 'AI가 내 조건에 맞는 종목을 고르고, 왜 골랐는지 쉬운 말로 알려 드립니다. <br/>아직 충족하지 못한 조건도 함께 보여 드려요.',
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
    desc: '캔들 한 개 읽는 법부터 시작하는 수업과 퀴즈, <br/>용어 사전으로 차트 보는 눈을 기르세요. 모두 무료입니다.',
    points: ['수업 6개 · 36단계', '퀴즈 36문제', '용어 사전 70개'],
    img: '/img/screen-3.webp',
    alt: '트레이닝 화면: 캔들 읽는 법 수업',
  },
  {
    id: 'settings',
    label: '내 설정',
    title: ['내 성향대로 시작하고,', '내 조건대로 고칩니다.'],
    desc: '안정형·균형형·공격형 중 하나로 시작하세요. 거래량, MACD 같은 보조지표를 켜고 끄고, 수치를 직접 바꿀 수 있습니다.',
    points: ['안정형', '균형형', '공격형'],
    img: '/img/screen-4.webp',
    alt: '내 설정 화면: 성향 선택과 보조지표 조절',
  },
];

const active = ref(FEATURES[0].id);
const sections = ref([]);
let io;

const go = (id) => {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  history.replaceState(null, '', `#${id}`);
};

onMounted(() => {
  // 화면 위쪽 40% 지점을 지나는 섹션을 '지금 보는 기능'으로 친다
  io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) if (e.isIntersecting) active.value = e.target.id;
    },
    { rootMargin: '-40% 0px -55% 0px' },
  );
  sections.value.forEach((el) => io.observe(el));
});
onBeforeUnmount(() => io?.disconnect());
</script>

<style scoped>
.wrap-wide { max-width: 1040px; margin: 0 auto; padding-left: 16px; padding-right: 16px; }

.eyebrow {
  margin: 0 0 14px;
  color: var(--brand);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: .08em;
}

/* 첫 화면 */
.hero { padding-top: 64px; padding-bottom: 48px; }
.hero h1 {
  margin: 0 0 20px;
  font-size: clamp(30px, 6vw, 52px);
  line-height: 1.25;
  letter-spacing: -0.025em;
  font-weight: 800;
}
.hero h1 span { display: block; color: var(--muted); }
.lead { margin: 0 0 28px; max-width: 560px; color: var(--sub); font-size: 17px; line-height: 1.7; }


/* 기능 바로가기 */
.feature-nav {
  position: sticky;
  top: 0;
  z-index: 5;
  background: color-mix(in srgb, var(--bg) 92%, transparent);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
}
.feature-nav .wrap-wide { display: flex; gap: 24px; overflow-x: auto; scrollbar-width: none; }
.feature-nav .wrap-wide::-webkit-scrollbar { display: none; }
.feature-nav a {
  flex: none;
  padding: 14px 0 12px;
  border-bottom: 2px solid transparent;
  color: var(--sub);
  font-size: 15px;
  text-decoration: none;
  white-space: nowrap;
}
.feature-nav a.on { color: var(--ink); font-weight: 600; border-bottom-color: var(--brand); }

/* 기능 섹션: 가운데 정렬, 번호 → 큰 제목 → 설명 → 화면 */
.feature { padding-top: 96px; text-align: center; scroll-margin-top: 48px; }
.num { margin: 0 0 14px; color: var(--brand); font-size: 14px; font-weight: 700; }
.num span { margin-right: 8px; color: var(--muted); font-weight: 500; }
.feature h2 {
  margin: 0 0 18px;
  font-size: clamp(28px, 5vw, 42px);
  line-height: 1.3;
  letter-spacing: -0.02em;
  font-weight: 800;
}
.desc { margin: 0 auto; max-width: 520px; color: var(--sub); font-size: 16px; line-height: 1.75; }
.points {
  display: flex; flex-wrap: wrap; justify-content: center; gap: 6px 20px;
  margin: 18px 0 0; padding: 0; list-style: none;
  color: var(--ink); font-size: 14px; font-weight: 600;
}
.points li::before { content: '✓'; margin-right: 6px; color: var(--brand); }

.shot {
  margin-top: 40px;
  padding: 48px 16px 0;
  border-radius: 28px;
  background: var(--panel);
  overflow: hidden;
  /* 폰 아래쪽은 패널 밖으로 잘라 시원하게 */
  max-height: 560px;
}
.shot img {
  display: block;
  width: min(340px, 82%);
  height: auto;
  margin: 0 auto;
}

/* 마무리 */
.closing { margin-top: 120px; padding: 88px 0; background: var(--panel); text-align: center; }
.closing h2 {
  margin: 0 0 28px;
  font-size: clamp(28px, 5vw, 42px);
  line-height: 1.3;
  letter-spacing: -0.02em;
  font-weight: 800;
  color: var(--panel-ink);
}

.notice { padding-top: 40px; padding-bottom: 56px; }
.notice h2 { margin: 0 0 8px; font-size: 15px; }
.notice ul { margin: 0; padding-left: 18px; color: var(--sub); font-size: 14px; }
.notice li { margin: 3px 0; }

@media (min-width: 720px) {
  .hero { padding-top: 112px; padding-bottom: 72px; }
  .feature { padding-top: 140px; }
  .shot { padding-top: 64px; max-height: 640px; }
  .shot img { width: 360px; }
}
</style>
