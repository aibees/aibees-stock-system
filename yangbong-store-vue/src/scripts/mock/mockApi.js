/**
 * 로컬 목업 API (VITE_MOCK=true 일 때만 켜진다 — `npm run dev:mock`).
 *
 * 서버(py-secret-api) 없이 온보딩·홈을 눈으로 확인하려고 aibeesApi 의 axios adapter 를 통째로 바꿔 끼운다.
 * 화면 코드는 그대로 두고 응답만 가짜다. 운영·dev 빌드에는 켜지지 않는다.
 *
 *   - 종목 이름·숫자는 전부 지어낸 값이다(실존 종목 아님). 같은 새로고침이면 같은 값이 나오게 시드 고정.
 *   - 등록되지 않은 경로는 404 로 거절한다(화면의 try/catch 가 "데이터 없음"으로 처리).
 *   - 비로그인 게스트 기준이라 권한(menus/my)은 빈 목록이다. 트레이닝은 정적 라우트라 메뉴 권한과 무관하다.
 */

import { evaluate, normalizeSettings, DEFAULT_SETTINGS } from '../indicators.js';
import { orderForType } from '../persona.js';
import { recoReasons } from '../recoReasons.js';
import { parseRate } from '../stockSignals.js';
import { chartQuizRoutes } from './mockChartQuiz.js';

export const MOCK_ENABLED = import.meta.env.VITE_MOCK === 'true';

/** 목업 기준일(최근 표시일). 고정해 두면 날짜가 지나도 화면이 같다. */
const BASE_YMD = '20261113';

/* ── 시드 고정 난수 ── */
const rng = (seed) => {
    let s = seed >>> 0;
    return () => {
        s = (s + 0x6D2B79F5) >>> 0;
        let t = s;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
};

/** 기준일까지 거슬러 올라가며 평일만 days 개. */
const tradingDates = (days) => {
    const y = Number(BASE_YMD.slice(0, 4)), m = Number(BASE_YMD.slice(4, 6)) - 1, d = Number(BASE_YMD.slice(6, 8));
    const cur = new Date(Date.UTC(y, m, d));
    const out = [];
    while (out.length < days) {
        const wd = cur.getUTCDay();
        if (wd !== 0 && wd !== 6) out.push(cur.toISOString().slice(0, 10));
        cur.setUTCDate(cur.getUTCDate() - 1);
    }
    return out.reverse();
};

const tickDown = (p) => {
    const tick = p < 2000 ? 1 : p < 5000 ? 5 : p < 20000 ? 10 : p < 50000 ? 50 : p < 200000 ? 100 : p < 500000 ? 500 : 1000;
    return Math.round(p / tick) * tick;
};

/** 일봉 chart_data 를 만든다. dayVol = 일 변동폭(비율), surge = 마지막 날 거래량 배수. */
const makeCandles = (seed, endClose, dayVol, surge) => {
    const rand = rng(seed);
    const dates = tradingDates(80);
    // 끝에서 거꾸로 걸어 올라가 종가가 endClose 로 끝나게 한다.
    const closes = [endClose];
    for (let i = 1; i < dates.length; i++) {
        const step = (rand() - 0.5) * 2 * dayVol;
        closes.unshift(closes[0] / (1 + step));
    }
    const baseVol = 400000 + Math.floor(rand() * 900000);
    return dates.map((date, i) => {
        const close = tickDown(closes[i]);
        const open = tickDown((i ? closes[i - 1] : close) * (1 + (rand() - 0.5) * dayVol * 0.6));
        const high = tickDown(Math.max(open, close) * (1 + rand() * dayVol * 0.6));
        const low = tickDown(Math.min(open, close) * (1 - rand() * dayVol * 0.6));
        const volume = Math.round(baseVol * (0.6 + rand() * 0.9) * (i === dates.length - 1 ? surge : 1));
        return { date, open, high, low, close, volume };
    });
};

/* ── 시장이 주목하는 종목(서버 순서 = 종합순위) ── */
const STOCKS = [
    { code: '900010', name: '한빛반도체', close: 71400, rate: 3.12, cap: 4210000, vol: 0.016, surge: 2.6, flags: { is_vol_surge: 'Y', is_bb_mid_breakout: 'Y', macd_cross: 'G' } },
    { code: '900020', name: '새벽바이오', close: 18650, rate: 8.74, cap: 310000, vol: 0.034, surge: 4.1, flags: { is_vol_surge: 'Y', obv_cross: 'G' } },
    { code: '900030', name: '대성에너지솔루션', close: 392000, rate: 1.55, cap: 9150000, vol: 0.012, surge: 1.8, flags: { is_bb_mid_breakout: 'Y', is_under_bb_upper: 'Y' } },
    { code: '900040', name: '푸른로보틱스', close: 42350, rate: 5.28, cap: 520000, vol: 0.028, surge: 3.2, flags: { is_vol_surge: 'Y', macd_cross: 'G', obv_cross: 'G' } },
    { code: '900050', name: '동해식품', close: 9870, rate: -0.80, cap: 180000, vol: 0.011, surge: 1.6, flags: { is_over_on_mid: 'Y', is_under_bb_upper: 'Y' } },
    { code: '900060', name: '미래모빌리티', close: 128500, rate: 2.40, cap: 2350000, vol: 0.019, surge: 2.2, flags: { is_bb_mid_breakout: 'Y', macd_cross: 'G' } },
    { code: '900070', name: '하늘소프트', close: 24100, rate: 6.61, cap: 240000, vol: 0.031, surge: 3.7, flags: { is_vol_surge: 'Y', is_bb_mid_breakout: 'Y' } },
];

// 주소에 ?reasons=all 을 붙이면 앞 3개를 "이유가 가장 많은 경우 / 대체 문구 / 이유 없음"으로 바꿔 모든 설명을 확인한다.
const REASON_PREVIEW = [
    { surge: 4.1, flags: { is_bb_mid_breakout: 'Y', macd_cross: 'G', obv_cross: 'G', is_under_bb_upper: 'Y' } },
    { surge: 1.0, flags: { is_vol_surge: 'Y', is_over_on_mid: 'Y', is_under_bb_upper: 'Y' } },
    { surge: 1.0, flags: {} },
];
const reasonPreview = () => new URLSearchParams(location.search).get('reasons') === 'all';
const buyTargets = () => STOCKS.map((s0, i) => {
    const s = reasonPreview() && REASON_PREVIEW[i] ? { ...s0, ...REASON_PREVIEW[i] } : s0;
    const chart = makeCandles(1000 + i, s.close, s.vol, s.surge);
    const last = chart[chart.length - 1];
    return {
        stock_code: s.code,
        stock_name: s.name,
        ymd: BASE_YMD,
        close: s.close,
        rate: `${s.rate > 0 ? '+' : ''}${s.rate.toFixed(2)}%`,
        market_cap: s.cap,
        open: last.open, high: last.high, low: last.low,
        volume: last.volume,
        chart_data: chart,
        is_vol_surge: 'N', is_bb_mid_breakout: 'N', is_over_on_mid: 'N', is_under_bb_upper: 'N',
        macd_cross: null, obv_cross: null,
        ...s.flags,
    };
});

/* ── 시황 ── */
const spark = (seed, start, drift) => {
    const rand = rng(seed);
    const out = [start];
    for (let i = 1; i < 20; i++) out.push(out[i - 1] * (1 + drift / 19 + (rand() - 0.5) * 0.012));
    return out.map(v => Math.round(v * 100) / 100);
};
// 주소에 ?weather=sunny|warm|cloudy|storm 을 붙이면 그 날씨가 나오게 오늘 등락률을 바꾼다(홈 날씨 확인용).
const WEATHER_RATES = { sunny: [2.1, 2.6], warm: [0.5, 0.3], cloudy: [-0.7, -0.4], storm: [-5.6, -6.8] };
const weatherOverride = () => WEATHER_RATES[new URLSearchParams(location.search).get('weather')] ?? null;
const marketSnapshot = (params) => {
    const w = weatherOverride();
    // extra=us10y 를 붙이면 달러 금리(미국 10년물)를 맨 앞에 더한다(실서버와 같게)
    const extra = String(params?.extra ?? '').split(',').includes('us10y')
        ? [{ key: 'us10y', label: '달러 금리', price: 4.912, rate: -2.77, change: -0.14, rate_20d: -1.2, spark: spark(4, 4.97, -0.012) }] : [];
    return [...extra, ...base()].map(m => (w && m.key === 'kospi' ? { ...m, rate: w[0] } : (w && m.key === 'kosdaq' ? { ...m, rate: w[1] } : m)));
};
const base = () => [
    { key: 'kospi', label: '코스피', price: 2684.31, rate: 1.12, rate_5d: 1.42, rate_20d: 3.85, spark: spark(1, 2585, 0.0385) },
    { key: 'kosdaq', label: '코스닥', price: 861.07, rate: 0.64, rate_5d: -0.63, rate_20d: 1.27, spark: spark(2, 850, 0.0127) },
    { key: 'usdkrw', label: '원/달러', price: 1382.5, rate: -0.34, change: -4.7, rate_5d: -0.4, rate_20d: 0.9, spark: spark(3, 1370, 0.009) },
];

/* ── 이번 주의 차트(/stocks/weekly-chart) ──
 * 운영은 서버(WeeklyChartService)가 전 주 추천 중 신호가 가장 선명한 종목을 고른다. 목업은 신호 3개가 걸린 푸른로보틱스를
 * 선정 시점 6거래일 전으로 두고, 선정 이후 봉까지 그대로 내려준다. 주소에 ?weekly=none 을 붙이면 블록이 숨는 경우(null)를 본다. */
const weeklyChart = () => {
    if (new URLSearchParams(location.search).get('weekly') === 'none') return null;
    const s = STOCKS[3];
    const chart = makeCandles(1003, s.close, s.vol, 1);   // 선정일 이후도 평범한 봉으로(성과를 꾸미지 않는다)
    const pickIdx = chart.length - 6;
    return {
        ymd: chart[pickIdx].date.replaceAll('-', ''),
        stock_code: s.code,
        stock_name: s.name,
        close: chart[pickIdx].close,
        lines: [
            '거래량이 전날보다 3.2배 늘었어요',
            '오르는 흐름으로 바뀌는 신호예요',
            '사려는 돈이 들어오고 있어요',
        ],
        bars: chart.slice(pickIdx - 39),
        marker_date: chart[pickIdx].date,
    };
};

/* ── 메뉴(권한 반영본과 라우트 등록용 전체 목록이 같다) ──
 * 주식 그룹(매수추천·개별주식·개별차트)과 공지(/board/notice). 개별주식·개별차트는 목업 데이터가 일부만 있다. */
const menu = (code, path, name, component, parents, children = []) => ({
    menu_code: code, menu_path: path, menu_name: name, menu_title: name, menu_component: component,
    menu_parents: parents, display_flag: 'Y', enabled_flag: 'Y', sort: 0, children,
});
const MENUS = [
    menu('Stocks', '/stock', '주식분석', 'StockView', 'root', [
        menu('StockBuyTarget', 'buy-target', '주목 종목', 'StockBuyTarget', 'Stocks'),
        menu('StockInfo', 'info', 'AI 분석', 'StockInfo', 'Stocks'),
        menu('ChartStock', 'chart', '차트 확인', 'ChartStock', 'Stocks'),
    ]),
    menu('Board', '/board', '공지', 'BoardView', 'root', [
        menu('NoticeList', 'notice', '공지사항', 'NoticeList', 'Board'),
        { ...menu('NoticeDetail', 'notice/detail', '공지 상세', 'NoticeDetail', 'Board'), display_flag: 'N' },
    ]),
];

/* ── 공지 ── */
const NOTICES = [
    { notice_id: 3, category: '업데이트', title: '트레이닝 탭이 생겼습니다', created_date: '2026-11-14 10:00:00',
      content: '<p>차트 보는 법과 기업분석 보는 법을 순서대로 익힐 수 있는 <b>트레이닝</b> 탭이 추가됩니다.</p><p>지금은 목차만 열려 있고 본문은 차례로 채웁니다.</p>' },
    { notice_id: 2, category: '공지', title: '시장이 주목하는 회사 화면을 바꿨습니다', created_date: '2026-11-12 09:30:00',
      content: '<p>내 성향에 맞춰 회사의 순서와 정리할 가격이 달라집니다.</p>' },
    { notice_id: 1, category: '점검', title: '11월 20일 새벽 서버 점검 안내', created_date: '2026-11-10 18:00:00',
      content: '<p>11월 20일 02:00~03:00 서버 점검이 있습니다.</p>' },
].map(n => ({ ...n, view_count: 0 }));

/* ── 종목 일봉: 분석 목록 종목 + 목록에서 빠진 관심 종목 확인용(900080) ── */
const CHART_ONLY = [{ code: '900080', close: 15320, vol: 0.02, surge: 2.4 }];
const stockChart = (code) => {
    const i = STOCKS.findIndex(s => s.code === code);
    const s = STOCKS[i] ?? CHART_ONLY.find(x => x.code === code);
    if (!s) return null;
    const rows = makeCandles(1000 + (i < 0 ? 50 : i), s.close, s.vol, s.surge);
    return {
        ohcl: rows.map(r => ({ x: r.date, o: r.open, h: r.high, l: r.low, c: r.close })),
        volume: rows.map(r => ({ x: r.date, y: r.volume })),
    };
};

/* ── 홈 AI 분석 종목(/stocks/buy-target/home) ──
 * 운영은 서버(HomePickService)가 계산한다. 목업은 그 정본인 화면 JS 로 같은 모양을 만든다. */
const homePicks = (params = {}) => {
    let settings = null;
    try { settings = params.settings ? JSON.parse(params.settings) : null; } catch { settings = null; }
    const s = normalizeSettings(settings ?? DEFAULT_SETTINGS);
    const all = buyTargets();
    const matched = all.filter(item => evaluate(item, s).match);
    const ordered = orderForType(matched, { order: s.order });
    const watch = new Set(String(params.watch || '').split(',').filter(Boolean));
    return {
        watch_items: all.filter(it => watch.has(it.stock_code)).map(it => ({ ...it, match: evaluate(it, s).match })),
        ymd: all[0]?.ymd ?? null,
        candidate_count: all.length,
        matched_count: matched.length,
        items: ordered.slice(0, Number(params.limit) || 3).map(it => {
            const r = recoReasons(it);
            return { stock_code: it.stock_code, stock_name: it.stock_name, ymd: it.ymd, close: it.close,
                rate_pct: parseRate(it.rate), reason: r.top ? r.top.text : null, reason_rest: r.rest };
        }),
    };
};

/* ── AI 분석 예시(지어낸 회사) ── */
const AI_UPDATED_AT = '2026-11-13T16:20:00+09:00';
const AI_ANALYSIS = {
    overview: {
        updated_at: AI_UPDATED_AT,
        content: [
            '**한빛반도체**는 반도체 후공정(패키징·테스트) 장비를 만드는 회사예요. 매출의 약 70%가 국내 대형 메모리 업체에서 나와요.',
            '',
            '- **매출**: 최근 4개 분기 연속 늘었어요. 고대역폭 메모리(HBM)용 장비 주문이 늘어난 영향이에요.',
            '- **이익**: 영업이익률이 12%대로, 1년 전(8%대)보다 좋아졌어요.',
            '- **재무 안정성**: 부채비율 45%로 낮은 편이에요.',
        ].join('\n'),
    },
    theme: {
        updated_at: AI_UPDATED_AT,
        content: [
            '- **HBM·AI 반도체**: AI 서버용 메모리 투자가 이어지며 관련 장비주가 함께 주목받고 있어요.',
            '- **후공정 국산화**: 해외 장비를 국산으로 바꾸려는 흐름의 수혜주로 묶여요.',
        ].join('\n'),
    },
    news: {
        updated_at: AI_UPDATED_AT,
        content: [
            '- **11/12 공시** — 국내 메모리 업체와 312억 원 규모 장비 공급 계약을 맺었어요(최근 매출의 약 9%).',
            '- **11/10 뉴스** — 3분기 실적이 시장 예상보다 좋았다는 분석이 나왔어요.',
        ].join('\n'),
    },
};

/* ── 라우트 표 ── */
const ok = (data) => ({ code: 200, message: 'mock', data });
// 인증 API 는 ApiResponse 형식({ success, data } / { success:false, error:{ message } })을 화면이 직접 본다
const okS = (data) => ({ success: true, data });
const failS = (message) => ({ success: false, error: { message } });
const mockBody = (c) => { try { return typeof c.data === 'string' ? JSON.parse(c.data) : (c.data || {}); } catch { return {}; } };
const mockLogin = (userId, userName) => {
    const b64 = (o) => btoa(JSON.stringify(o)).replace(/=+$/, '');
    return {
        accessToken: `${b64({ alg: 'HS256' })}.${b64({ sub: String(userId), exp: Math.floor(Date.now() / 1000) + 3600 })}.mock`,
        refreshToken: 'mock-refresh',
        loginInfo: { user_id: String(userId), user_name: userName, role: ['STOCK_USER'] },
    };
};
// 계정의 학습 기록·주식분석 동의(목업 서버 메모리 — 새로고침하면 비워진다). 처음엔 계정에만 있는 단계 하나를 넣어 둔다.
const MOCK_TRAINING = { done: [{ stage_key: 'chart-basic/candle', done_at: Date.now() - 86400000 }], stock_notice: null };
// 꿀(포인트) 서버 흉내 — 규칙은 py-yangbong-api honey_service.py 와 같다(목업 메모리, 새로고침하면 처음으로).
const HONEY = { ledger: [{ id: 3, amount: 300, kind: 'LESSON', ref: 'seed', at: Date.now() - 2 * 86400000 },
    { id: 2, amount: 930, kind: 'START', ref: 'seed', at: Date.now() - 3 * 86400000 }],
    attendDays: [1, 2, 3, 4].map(d => new Date(Date.now() - d * 86400000).toDateString()), passUntil: null, nextId: 10, lessons: 1 };
const honeyToday = () => HONEY.ledger.filter(r => new Date(r.at).toDateString() === new Date().toDateString());
const honeyAdReward = (n) => [20, 30, 40][n] ?? 30;
const honeyAdd = (amount, kind) => { HONEY.ledger.unshift({ id: HONEY.nextId++, amount, kind, ref: '', at: Date.now() }); return amount; };
const honeyStreak = () => {
    let n = 0; const d = new Date();
    if (!HONEY.attendDays.includes(d.toDateString())) d.setDate(d.getDate() - 1);
    while (HONEY.attendDays.includes(d.toDateString())) { n++; d.setDate(d.getDate() - 1); }
    return n;
};
const honeySummary = () => {
    const t = honeyToday();
    const ad = t.filter(r => r.kind === 'AD').length;
    return { balance: HONEY.ledger.reduce((a, r) => a + r.amount, 0), expiringSoon: 0,
        today: { earned: t.filter(r => r.amount > 0).reduce((a, r) => a + r.amount, 0), target: 360 },
        attend: { done: t.some(r => r.kind === 'ATTEND'), amount: 10 }, streak: { days: honeyStreak(), goal: 7, bonus: 50 },
        quiz: { done: t.some(r => r.kind === 'QUIZ'), amount: 10 }, ad: { count: ad, max: 10, next: ad < 10 ? honeyAdReward(ad) : 0 },
        lesson: { done: HONEY.lessons, total: 37, amount: 20 }, start: { done: true, amount: 100 },
        dayPass: { cost: 1000, until: HONEY.passUntil && HONEY.passUntil > Date.now() ? HONEY.passUntil : null } };
};
const honeyOk = (gained) => ok({ summary: honeySummary(), gained });
// 오늘의 경제 이슈(목업 — 실제는 관리자 검토 후 공개된 것만 온다)
const MOCK_ISSUE = {
    ymd: '20261122', status: 'PUBLISHED', title: '미국 반도체 주식이 크게 떨어지며 코스피·코스닥도 함께 약했어요', keywords: ['반도체', '미국증시'],
    what: '금요일 밤 미국에서 반도체 회사 주가가 한꺼번에 내렸어요. 우리 시장에서도 반도체 비중이 큰 대형주가 따라 내리면서 지수가 크게 떨어졌어요.',
    why: ['코스피에서 반도체 회사가 차지하는 몫이 커서, 반도체가 흔들리면 지수 전체가 흔들려요.', '이런 날은 하루 움직임만 보기보다 며칠 흐름을 함께 보는 게 좋아요.'],
    term: { name: '동반 약세', desc: '여러 시장이나 종목이 같은 날 함께 내리는 것을 말해요.' },
    sources: [{ title: '미 반도체주 급락에 코스피 하락 마감', press: '목업경제', url: 'https://example.com/a' }, { title: '외국인 순매도 확대… 대형 반도체주 약세', press: '목업일보', url: 'https://example.com/b' }],
    sectorYmd: '20261120',
    sectors: [
        { market: 'KOSPI', sector_cd: '0017', sector_name: '조선', chg_rate: 4.12, leaders: ['한빛조선', '동해중공업', '바다엔진'], why: '대형 선박 수주 소식이 이어지며 업종 전체가 함께 올랐어요.' },
        { market: 'KOSPI', sector_cd: '0021', sector_name: '방산', chg_rate: 3.21, leaders: ['한결에어로', '대한방위', '미래시스템'], why: '해외 수출 계약 기대가 커지며 관련 회사들이 강했어요.' },
        { market: 'KOSDAQ', sector_cd: '1009', sector_name: '전기·전자', chg_rate: 2.64, leaders: ['새빛전기', '한전설비', '그린케이블'], why: '' },
    ],
};
const honeyHasPass = () => !!(HONEY.passUntil && HONEY.passUntil > Date.now());
// 친구 초대(2단계) — 넣을 수 있는 친구 코드는 BEEFRIEND 하나(목업)
const INVITE = { code: '7692B7FB', completed: 2, pending: 1, month: 2, mine: null };
const inviteSummary = () => ({ code: INVITE.code, reward: { inviter: 300, invitee: 100, days: 3 }, completed: INVITE.completed,
    pending: INVITE.pending, monthLeft: 10 - INVITE.month, monthMax: 10, mine: INVITE.mine, canRedeem: !INVITE.mine });

const ROUTES = [
    ...chartQuizRoutes({ ok, body: (c) => mockBody(c), hasPass: () => honeyHasPass(), honeyAdd: (a, k) => honeyAdd(a, k) }),
    ['GET', '/api/v1/honey', () => ok(honeySummary())],
    ['GET', '/api/v1/honey/ledger', () => ok(HONEY.ledger.slice(0, 50))],
    ['GET', '/api/v1/honey/invite', () => ok(inviteSummary())],
    ['POST', '/api/v1/honey/invite/redeem', (c) => {
        const code = String(mockBody(c).code || '').toUpperCase();
        if (code === INVITE.code) return { __error: 409, message: '내 초대 코드는 넣을 수 없어요.' };
        if (code !== 'BEEFRIEND') return { __error: 409, message: '없는 초대 코드예요.' };
        INVITE.mine = { code, days: 1, goal: 3, completed: false };
        return ok({ invite: inviteSummary(), summary: honeySummary(), gained: 0 });
    }],
    ['POST', '/api/v1/honey/attend', () => {
        if (honeySummary().attend.done) return honeyOk(0);
        HONEY.attendDays.push(new Date().toDateString());
        let g = honeyAdd(10, 'ATTEND');
        if (honeyStreak() % 7 === 0) g += honeyAdd(50, 'STREAK');
        return honeyOk(g);
    }],
    ['POST', '/api/v1/honey/quiz', () => honeyOk(honeySummary().quiz.done ? 0 : honeyAdd(10, 'QUIZ'))],
    ['POST', '/api/v1/honey/start', () => honeyOk(0)],
    ['POST', '/api/v1/honey/mock-ad', () => { const s = honeySummary(); return honeyOk(s.ad.count < 10 ? honeyAdd(s.ad.next, 'AD') : 0); }],
    ['POST', '/api/v1/honey/spend', () => {
        if (honeySummary().balance < 1000) return null;
        honeyAdd(-1000, 'SPEND_DAY_PASS');
        HONEY.passUntil = Math.max(HONEY.passUntil ?? 0, Date.now()) + 24 * 3600 * 1000;
        return honeyOk(-1000);
    }],
    ['GET', '/api/v1/training/progress', () => okS(MOCK_TRAINING)],
    ['POST', '/api/v1/training/progress', (c) => {
        let honeyGained = 0;
        for (const k of mockBody(c).stage_keys || []) {
            if (!MOCK_TRAINING.done.some(r => r.stage_key === k)) {
                MOCK_TRAINING.done.push({ stage_key: k, done_at: Date.now() });
                honeyGained += honeyAdd(20, 'LESSON'); HONEY.lessons += 1;
            }
        }
        return okS({ ...MOCK_TRAINING, honeyGained });
    }],
    ['POST', '/api/v1/training/stock-notice', (c) => {
        MOCK_TRAINING.stock_notice = { version: String(mockBody(c).version), agreed_at: Date.now() };
        return okS(MOCK_TRAINING);
    }],
    ['GET', '/api/v1/daily-issue', () => ok({ issue: MOCK_ISSUE, past: [
        { ymd: '20261121', title: '원/달러 환율이 1,340원대로 올랐어요' },
        { ymd: '20261120', title: '미국이 금리를 그대로 두고 다음 회의에 관심이 모였어요' },
    ] })],
    ['GET',/^\/api\/v1\/daily-issue\/(\d{8})$/, (c, m) => ok({ ...MOCK_ISSUE, ymd: m[1] })],
    ['GET', '/api/v1/indicators/market-snapshot', (c) => ok(marketSnapshot(c.params))],
    ['GET', '/api/v1/stocks/weekly-chart', () => ok(weeklyChart())],
    ['GET', '/api/v1/stocks/buy-target/home', (c) => ok(homePicks(c.params))],
    ['GET', '/api/v1/stocks/buy-target', () => ok(buyTargets())],
    ['GET', '/api/v1/charts/stock', (c) => {
        const chart = stockChart(c.params?.stock_code);
        return chart ? ok(chart) : null;
    }],
    // 계정 설정·계정 삭제(로그인 흉내: sessionStorage userSession 을 직접 넣어 확인한다)
    ['GET', '/api/v1/user-options', () => ok({ user_master: { email: 'tester@example.com' }, user_detail: {}, user_options: {} })],
    ['DELETE', '/api/oauth/account', () => ok(null)],
    // 아이디 로그인·회원가입(2026-11-20). 인증코드는 항상 123456, 이미 있는 아이디는 aibees1129·tester.
    ['POST', '/api/oauth/signup/login-id/check', (c) => {
        const id = String(mockBody(c).loginId || '').toLowerCase();
        const taken = ['aibees1129', 'tester'].includes(id);
        return okS({ loginId: id, available: !taken, message: taken ? '이미 사용 중인 아이디예요.' : '사용할 수 있는 아이디예요.' });
    }],
    ['POST', '/api/oauth/signup/code', () => okS({ verifyToken: 'mock-verify', expiresIn: 600 })],
    ['POST', '/api/oauth/signup/code/verify', (c) => (mockBody(c).code === '123456'
        ? okS({ verifiedToken: 'mock-verified', email: 'new@example.com', expiresIn: 1800 })
        : failS('인증코드가 맞지 않아요. (4번 남음)'))],
    ['POST', '/api/oauth/signup', (c) => (mockBody(c).verifiedToken === 'mock-verified' && mockBody(c).loginId
        ? okS(mockLogin(7, mockBody(c).userName || '신규')) : failS('이메일 인증을 먼저 해 주세요.'))],
    // 아이디·비밀번호 찾기: 코드 123456, 가입된 아이디 aibees1129(마스킹 ai******29), 비밀번호 재설정은 아이디 tester
    ['POST', '/api/oauth/find-id/code', () => okS({ verifyToken: 'mock-find', expiresIn: 600 })],
    ['POST', '/api/oauth/find-id/verify', (c) => (mockBody(c).code === '123456'
        ? okS({ maskedLoginIds: ['ai******29'] }) : failS('인증코드가 맞지 않아요. (4번 남음)'))],
    ['POST', '/api/oauth/password/code', () => okS({ verifyToken: 'mock-reset', expiresIn: 600 })],
    ['POST', '/api/oauth/password/reset-by-code', (c) => {
        const b = mockBody(c);
        if (b.code !== '123456') return failS('인증코드가 맞지 않아요. (4번 남음)');
        return b.loginId === 'tester' ? okS(null) : failS('아이디와 이메일이 일치하지 않아요.');
    }],
    ['POST', '/api/oauth/email', (c) => (mockBody(c).loginId === 'tester' && mockBody(c).pswd
        ? okS(mockLogin(7, '테스터')) : failS('사용자를 찾을 수 없습니다.'))],
    ['GET', '/api/v1/notices', () => ok(NOTICES.map(({ content, ...rest }) => rest))],
    ['GET', /^\/api\/v1\/notices\/(\d+)$/, (c, m) => {
        const n = NOTICES.find(x => x.notice_id === Number(m[1]));
        return n ? ok(n) : null;
    }],
    // AI 분석(종목 상세 'AI 견해' 탭). 내용은 지어낸 회사(한빛반도체) 기준 예시 문장이다 — 다른 종목도 같은 글을 돌려준다.
    ['GET', '/api/v1/anthropic/stock-analysis/overview', () => ok(AI_ANALYSIS.overview)],
    ['GET', '/api/v1/anthropic/stock-analysis/theme', () => ok(AI_ANALYSIS.theme)],
    ['GET', '/api/v1/anthropic/stock-analysis/news', () => ok(AI_ANALYSIS.news)],
    // 라우트 등록용 전체 메뉴·내 권한(홈·온보딩·트레이닝·메뉴는 정적 라우트).
    ['GET', '/api/v1/master/menus/my', () => ok({ menus: MENUS, features: honeyHasPass() ? ['RECO_ADVANCED'] : [], roles: [], settings: {} })],
    ['GET', '/api/v1/master/menus', () => ok(MENUS)],
];

const LATENCY_MS = 220;   // 스켈레톤이 잠깐이라도 보이게

/** axios adapter. config.url 은 baseURL 없이 경로만 들어온다. */
export const mockAdapter = (config) => new Promise((resolve, reject) => {
    const method = String(config.method || 'get').toUpperCase();
    const path = String(config.url || '').split('?')[0];
    let match = null;
    const hit = ROUTES.find(([m, p]) => m === method && (match = p instanceof RegExp ? path.match(p) : (p === path ? [] : null)));
    setTimeout(() => {
        const body = hit ? hit[2](config, match) : null;
        if (body?.__error) {   // 목업 오류 응답: { __error: 상태코드, message }
            const error = new Error(body.message);
            error.config = config;
            error.response = { status: body.__error, statusText: 'Error', data: { success: false, error: { message: body.message, code: body.code } }, headers: {}, config };
            reject(error);
            return;
        }
        if (body) {
            resolve({ data: body, status: 200, statusText: 'OK', headers: {}, config, request: {} });
            return;
        }
        console.info(`[mock] 목업 없음 → 404: ${method} ${path}`);
        const error = new Error(`mock: ${method} ${path} 없음`);
        error.config = config;
        error.response = { status: 404, statusText: 'Not Found', data: { code: 404, message: 'mock not found' }, headers: {}, config };
        reject(error);
    }, LATENCY_MS);
});
