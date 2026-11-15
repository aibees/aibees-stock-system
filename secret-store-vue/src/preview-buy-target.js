// 매수추천(StockBuyTarget) 단계 확인용 하네스. 로그인/서버 없이 목업 API 로 단독 렌더링한다.
// 목업 API 는 서버(RecoLevel.py)가 하는 일을 흉내 낸다: 열람 단계 밖 종목은 빼고, 기본 단계에는 고급 필드를 지운다.
import { createApp, h } from 'vue';
import { createPinia } from 'pinia';
import { createRouter, createMemoryHistory, RouterView } from 'vue-router';
import aibeesApi from './scripts/aibeesApi.js';
import StockBuyTarget from './components/Stocks/StockBuyTarget.vue';

const bars = (c) => Array.from({ length: 8 }, (_, i) => {
    const b = c * (0.9 + i * 0.012);
    return { date: '2026-11-0' + (i + 1), open: b * 0.99, high: b * 1.02, low: b * 0.97, close: b, volume: 1e6 + i * 1e5 };
});
// stages: 이 종목이 속한 알고리즘 단계. 1 = 옛 기계식(rank_no 있음), 2 = 2파(종합순위·모델 확률·수급 있음)
const mk = (n, code, sector, close, rate, stages, no) => ({
    stock_name: n, stock_code: code, sector_name: sector, close, open: close * 0.98, high: close * 1.03, low: close * 0.97,
    rate, chart_data: bars(close), _stages: stages,
    rank_no: stages.includes(1) ? no : null, score: stages.includes(1) ? 90 - no * 4 : null,
    composite_rank_no: stages.includes(2) ? no : null, shape_proba: stages.includes(2) ? 0.9 - no * 0.03 : null,
    frgn_amt: 120 - no * 10, orgn_amt: 40, prsn_amt: -160, investor_ymd: '20261112',
});
const all = [
    mk('삼성전자', '005930', '반도체', 78400, '2.10%', [1, 2], 1),
    mk('SK하이닉스', '000660', '반도체', 201500, '1.40%', [2], 2),
    mk('에코프로', '086520', '2차전지', 72000, '-0.80%', [1], 3),
    mk('한미반도체', '042700', '반도체', 98000, '3.20%', [1], 4),
    mk('NAVER', '035420', '인터넷', 210000, '0.50%', [2], 5),
    mk('카카오', '035720', '인터넷', 52000, '0.90%', [1, 2], 6),
];

const level = Number(new URLSearchParams(location.search).get('level') || 1);
aibeesApi.get = async () => {
    const rows = all.map(({ _stages, ...r }) => ({ ...r, reco_stages: _stages.filter((s) => s <= level) }))
        .filter((r) => r.reco_stages.length);
    if (level < 2) {
        rows.forEach((r) => ['shape_proba', 'composite_rank_no', 'frgn_amt', 'orgn_amt', 'prsn_amt', 'investor_ymd'].forEach((k) => delete r[k]));
    }
    return { data: { data: rows } };
};

const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: StockBuyTarget }, { path: '/:p(.*)*', component: { render: () => null } }],
});
await router.push('/' + location.search);
createApp({ render: () => h(RouterView) }).use(createPinia()).use(router).mount('#app');
