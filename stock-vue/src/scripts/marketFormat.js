/**
 * 시가총액·투자자 순매수 표기 (매수추천 StockBuyTarget.vue · 주식 차트 ChartStock.vue 공용).
 *
 * 서버 단위: 시가총액 = 억원, 순매수 대금 = 백만원, 순매수 수량 = 주
 *   (stock_investor_daily / StockService.attach_market_info)
 * 색: 순매수(+) = 빨강(.up), 순매도(−) = 파랑(.down) — 앱 공통 등락색과 같다.
 */

// 억원 → "1,537조 5,711억" / "3,479억"
export const formatEok = (eok) => {
    const v = Math.round(Math.abs(eok));
    const jo = Math.floor(v / 10000);
    const rest = v % 10000;
    if (jo === 0) return `${rest.toLocaleString()}억`;
    return rest ? `${jo.toLocaleString()}조 ${rest.toLocaleString()}억` : `${jo.toLocaleString()}조`;
};

// 목록 한 줄용 짧은 시가총액(억원) → "1,538조" / "4.2조" / "8,500억"
export const formatCapShort = (eok) => {
    if (eok == null) return '';
    if (eok >= 100000) return `${Math.round(eok / 10000).toLocaleString()}조`;
    if (eok >= 10000) return `${(eok / 10000).toFixed(1)}조`;
    return `${Math.max(1, Math.round(eok)).toLocaleString()}억`;
};

// 순매수 대금(백만원) → "+3,479억" / "−4,800만". 1억 미만은 만원 단위
export const formatNetAmt = (mil) => {
    if (!mil) return '0';
    const sign = mil > 0 ? '+' : '−';
    const eok = Math.abs(mil) / 100;
    const body = eok >= 1 ? formatEok(eok) : `${(Math.abs(mil) * 100).toLocaleString()}만`;
    return sign + body;
};

// 좁은 칸용 순매수 대금(백만원) → "+1.1조" / "+3,479억" / "−4,800만"
export const formatNetAmtShort = (mil) => {
    if (mil == null) return '–';
    if (!mil) return '0';
    const sign = mil > 0 ? '+' : '−';
    const eok = Math.abs(mil) / 100;
    if (eok >= 10000) return `${sign}${(eok / 10000).toFixed(1)}조`;
    if (eok >= 1) return `${sign}${Math.round(eok).toLocaleString()}억`;
    return `${sign}${(Math.abs(mil) * 100).toLocaleString()}만`;
};

// PER/PBR(배치가 문자열로 저장) → "12.3" / "217" / PER 음수는 "적자" / 값 없음·0 은 "–"
export const formatRatio = (v, { lossLabel = null } = {}) => {
    const n = Number(v);
    if (v == null || v === '' || Number.isNaN(n) || n === 0) return '–';
    if (n < 0 && lossLabel) return lossLabel;
    const a = Math.abs(n);
    return (n < 0 ? '−' : '') + (a >= 100 ? Math.round(a).toLocaleString() : a.toFixed(a >= 10 ? 1 : 2));
};

// 순매수 수량(주) → "+130.7만주" / "−5,200주"
export const formatNetQty = (qty) => {
    if (!qty) return '0주';
    const sign = qty > 0 ? '+' : '−';
    const v = Math.abs(qty);
    return sign + (v >= 10000 ? `${(v / 10000).toFixed(1)}만주` : `${v.toLocaleString()}주`);
};

export const signClass = (v) => (v > 0 ? 'up' : v < 0 ? 'down' : '');

// "20261008" → "10/8"
export const shortYmd = (ymd) => (ymd ? `${Number(ymd.slice(4, 6))}/${Number(ymd.slice(6, 8))}` : '');
