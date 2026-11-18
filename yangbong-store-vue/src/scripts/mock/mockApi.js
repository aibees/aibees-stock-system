/**
 * 로컬 목업 API (VITE_MOCK=true 일 때만 켜진다 — `npm run dev:mock`).
 *
 * 서버(py-naver-stock-theme) 없이 온보딩·홈을 눈으로 확인하려고 aibeesApi 의 axios adapter 를 통째로 바꿔 끼운다.
 * 화면 코드는 그대로 두고 응답만 가짜다. 운영·dev 빌드에는 켜지지 않는다.
 *
 *   - 종목 이름·숫자는 전부 지어낸 값이다(실존 종목 아님). 같은 새로고침이면 같은 값이 나오게 시드 고정.
 *   - 등록되지 않은 경로는 404 로 거절한다(화면의 try/catch 가 "데이터 없음"으로 처리).
 *   - 비로그인 게스트 기준이라 권한(menus/my)은 빈 목록이다. 트레이닝은 정적 라우트라 메뉴 권한과 무관하다.
 */

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
const marketSnapshot = () => {
    const w = weatherOverride();
    return base().map(m => (w && m.key === 'kospi' ? { ...m, rate_1d: w[0] } : (w && m.key === 'kosdaq' ? { ...m, rate_1d: w[1] } : m)));
};
const base = () => [
    { key: 'kospi', label: '코스피', price: 2684.31, rate_1d: 1.12, rate_5d: 1.42, rate_20d: 3.85, spark: spark(1, 2585, 0.0385) },
    { key: 'kosdaq', label: '코스닥', price: 861.07, rate_1d: 0.64, rate_5d: -0.63, rate_20d: 1.27, spark: spark(2, 850, 0.0127) },
    { key: 'usdkrw', label: '원/달러', price: 1382.5, rate: -0.34, change: -4.7 },
];

/* ── 지난달 성과 ── */
const performance = () => ({
    ym: '202610',
    hold_days: 5,
    top_pct: 20,
    top_count: 6,
    top_avg_return: 14.8,
    evaluated_count: 31,
    avg_return: 6.2,
    top_list: [
        { stock_code: '900110', stock_name: '은하디스플레이', ymd: '20261008', entry_price: 15200, peak_ymd: '20261013', peak_price: 18950, max_return: 24.7 },
        { stock_code: '900120', stock_name: '청솔제약', ymd: '20261015', entry_price: 53800, peak_ymd: '20261020', peak_price: 64100, max_return: 19.1 },
        { stock_code: '900130', stock_name: '태양전기', ymd: '20261006', entry_price: 8420, peak_ymd: '20261008', peak_price: 9850, max_return: 17.0 },
        { stock_code: '900140', stock_name: '누리네트웍스', ymd: '20261022', entry_price: 31400, peak_ymd: '20261027', peak_price: 36200, max_return: 15.3 },
        { stock_code: '900150', stock_name: '바다조선', ymd: '20261012', entry_price: 77100, peak_ymd: '20261016', peak_price: 86500, max_return: 12.2 },
    ],
});

/* ── 메뉴(권한 반영본과 라우트 등록용 전체 목록이 같다) ──
 * 주식 그룹(매수추천·개별주식·개별차트)과 공지(/board/notice). 개별주식·개별차트는 목업 데이터가 일부만 있다. */
const menu = (code, path, name, component, parents, children = []) => ({
    menu_code: code, menu_path: path, menu_name: name, menu_title: name, menu_component: component,
    menu_parents: parents, display_flag: 'Y', enabled_flag: 'Y', sort: 0, children,
});
const MENUS = [
    menu('Stocks', '/stock', '주식분석', 'StockView', 'root', [
        menu('StockBuyTarget', 'buy-target', '매수추천', 'StockBuyTarget', 'Stocks'),
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

/* ── 라우트 표 ── */
const ok = (data) => ({ code: 200, message: 'mock', data });
const ROUTES = [
    ['GET', '/api/v1/indicators/market-snapshot', () => ok(marketSnapshot())],
    ['GET', '/api/v1/stocks/buy-target/performance', () => ok(performance())],
    ['GET', '/api/v1/stocks/buy-target', () => ok(buyTargets())],
    ['GET', '/api/v1/charts/stock', (c) => {
        const chart = stockChart(c.params?.stock_code);
        return chart ? ok(chart) : null;
    }],
    ['GET', '/api/v1/notices', () => ok(NOTICES.map(({ content, ...rest }) => rest))],
    ['GET', /^\/api\/v1\/notices\/(\d+)$/, (c, m) => {
        const n = NOTICES.find(x => x.notice_id === Number(m[1]));
        return n ? ok(n) : null;
    }],
    // 라우트 등록용 전체 메뉴·내 권한(홈·온보딩·트레이닝·메뉴는 정적 라우트).
    ['GET', '/api/v1/master/menus/my', () => ok({ menus: MENUS, features: [], roles: [], settings: {} })],
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
