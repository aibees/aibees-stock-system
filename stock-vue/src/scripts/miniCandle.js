/**
 * 간이 봉차트(최근 120영업일 + 20/60/120일선) — 홈·매수추천·개별주식이 같이 쓴다.
 * 데이터는 /stocks/buy-target 한 행의 chart_data. CandlestickChart 컴포넌트에 그대로 넘긴다.
 *
 * 색: 캔들은 앱 공통 등락색(상승 #C8282A / 하락 #1F5BD1, ChartStock.vue 와 동일),
 *     이동평균선은 범례(MINI_LEGEND)와 같은 값을 쓴다.
 */

export const MINI_LEGEND = [
    { label: 'MA20',  color: '#efa55b' },
    { label: 'MA60',  color: '#8bb400' },
    { label: 'MA120', color: '#01b6f3' },
];

export const buyTargetCandleData = (item) => {
    const rows = item?.chart_data || [];
    const toXY = (key) => rows.map(r => ({
        x: (r.date || '').slice(0, 10),
        y: r[key] != null ? Number(r[key]) : null,
    }));
    const [ma20, ma60, ma120] = MINI_LEGEND;

    return {
        labels: rows.map(r => (r.date || '').slice(0, 10)),
        datasets: [
            {
                label: 'Candle',
                data: rows.map(r => ({
                    x: (r.date || '').slice(0, 10),
                    o: Number(r.open), h: Number(r.high), l: Number(r.low), c: Number(r.close),
                })),
                color: { up: '#C8282A', down: '#1F5BD1', unchanged: '#9A8C7E' },
            },
            { label: ma20.label,  data: toXY('ma20'),  borderColor: ma20.color,  type: 'line', pointRadius: 0 },
            { label: ma60.label,  data: toXY('ma60'),  borderColor: ma60.color,  type: 'line', pointRadius: 0 },
            { label: ma120.label, data: toXY('ma120'), borderColor: ma120.color, type: 'line', pointRadius: 0 },
        ],
    };
};

// 미니 프리뷰용 — 줌/팬 비활성화, 범례는 화면 쪽 커스텀 legend 로 대체, 축은 최소화
export const miniCandleOptions = {
    plugins: {
        legend: { display: false },
        zoom: {
            pan: { enabled: false },
            zoom: { wheel: { enabled: false }, pinch: { enabled: false } },
        },
    },
    scales: {
        // x축 display:false 를 바로 주면(Chart.js 3.9 + category 스케일) 범위(min/max) 계산 자체가
        // 깨져서 데이터가 거의 안 보이는 버그가 있다 — 축은 켜두고 눈금표시(ticks)만 숨긴다.
        x: { type: 'category', grid: { display: false }, ticks: { display: false } },
        y: { position: 'right', beginAtZero: false, ticks: { font: { size: 9 } } },
    },
};
