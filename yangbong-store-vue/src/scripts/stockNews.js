/**
 * 관심 종목의 오늘 소식 판단. 분석 목록의 일봉(chart_data)과 내 조건 판정으로 사실만 한 줄로 만든다.
 * 매수·매도를 권하는 표현은 쓰지 않는다. 발송 서버를 붙일 때도 같은 규칙을 기준으로 삼는다.
 */
import { numOrNull, parseRate, volumeFacts } from './stockSignals.js';

export const NEWS_RULES = { volumeRatio: 2, priceMovePct: 5, lookbackDays: 20 };

const average = (list) => list.reduce((a, b) => a + b, 0) / list.length;

/** 차트 API 응답을 분석 목록 항목 모양으로 바꾼다. 오늘 목록에서 빠진 관심 종목의 소식 판단에 쓴다. */
export const itemFromChart = (code, name, chart) => {
    const candles = chart?.ohcl ?? [];
    if (!candles.length) return null;
    const volumes = new Map((chart.volume ?? []).map(v => [v.x, v.y]));
    const chart_data = candles.map(c => ({ date: c.x, open: c.o, high: c.h, low: c.l, close: c.c, volume: volumes.get(c.x) ?? null }));
    const last = chart_data.at(-1);
    const prevClose = chart_data.at(-2)?.close;
    return {
        stock_code: code,
        stock_name: name,
        ymd: String(last.date).slice(0, 10).replaceAll('-', ''),
        close: last.close,
        rate: prevClose ? `${((last.close - prevClose) / prevClose * 100).toFixed(2)}%` : null,
        volume: last.volume,
        chart_data,
    };
};

export const judgeStockNews = (item, evaluation = null) => {
    const ymd = String(item?.ymd ?? '').replaceAll('-', '');
    const bars = (item?.chart_data ?? [])
        .filter(r => !ymd || String(r.date ?? '').slice(0, 10).replaceAll('-', '') <= ymd)
        .map(r => ({ close: numOrNull(r.close), high: numOrNull(r.high) }))
        .filter(r => r.close !== null);
    const n = NEWS_RULES.lookbackDays;
    const last = bars.at(-1);
    const prev = bars.slice(-n - 1, -1);
    const out = [];

    const ratio = volumeFacts(item).avgRatio;
    if (ratio !== null && ratio >= NEWS_RULES.volumeRatio) {
        out.push({ kind: 'volume', text: `거래량이 평소보다 ${ratio.toFixed(1)}배 늘었어요` });
    }
    if (last && prev.length >= n) {
        const highs = prev.map(r => r.high ?? r.close);
        if (last.close > Math.max(...highs)) out.push({ kind: 'high', text: `최근 ${n}거래일 중 가장 높은 가격에 마감했어요` });

        const avgNow = average([...prev.slice(1), last].map(r => r.close));
        const prevClose = prev.at(-1).close;
        const avgPrev = average(prev.map(r => r.close));
        if (prevClose <= avgPrev && last.close > avgNow) out.push({ kind: 'above-ma', text: `${n}일 평균 가격 위로 올라섰어요` });
        if (prevClose >= avgPrev && last.close < avgNow) out.push({ kind: 'below-ma', text: `${n}일 평균 가격 아래로 내려왔어요` });
    }
    const rate = parseRate(item?.rate);
    if (rate !== null && Math.abs(rate) >= NEWS_RULES.priceMovePct) {
        out.push({ kind: 'price', text: `오늘 ${Math.abs(rate).toFixed(1)}% ${rate > 0 ? '올랐어요' : '내렸어요'}` });
    }
    if (evaluation?.match) out.push({ kind: 'match', text: '오늘 내 조건에 맞는 종목이에요' });

    return out[0] ?? { kind: 'quiet', text: '오늘은 큰 변화가 없어요' };
};
