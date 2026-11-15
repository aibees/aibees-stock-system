/**
 * 매도 지정가 표시/검증용 순수 함수 (화면 의존 없음 — 단위 검증 가능).
 *
 * 방향(trigger):
 *   UP   익절 — 체결가가 지정가 "이상"이 되면 매도
 *   DOWN 손절 — 체결가가 지정가 "이하"가 되면 매도
 * 백엔드: py-stock-batch app/trade_worker/sell_executor.py (tier_hit / pick_manual_tier),
 *         sql/27_manual_sell_trigger_ddl.sql.
 */

export const TRIGGER_LABEL = { UP: '익절', DOWN: '손절' };
export const TRIGGER_DESC = { UP: '이상이면 매도', DOWN: '이하이면 매도' };

const num = (v) => {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
};

/** 행의 방향. 서버가 trigger_type 을 안 주는 구행(sql/27 미적용)은 UP. */
export const triggerOf = (tier) => (String(tier?.trigger_type ?? 'UP').toUpperCase() === 'DOWN' ? 'DOWN' : 'UP');

/** price 가 base 대비 몇 %인가(소수 1자리로 반올림 전의 실수). base/price 가 없거나 0 이하면 null. */
export const pctVs = (price, base) => {
    const p = num(price);
    const b = num(base);
    if (p === null || b === null || p <= 0 || b <= 0) return null;
    return (p / b - 1) * 100;
};

/** +25.9% / -8.0% / 0.0%  (null 이면 빈 문자열) */
export const formatPct = (pct) => {
    if (pct === null || pct === undefined || !Number.isFinite(pct)) return '';
    const r = Math.round(pct * 10) / 10;
    return `${r > 0 ? '+' : ''}${r.toFixed(1)}%`;
};

/** 색 구분: 상승(+)=up, 하락(-)=down, 0/없음=flat  (한국 시장 관례: 상승 적색, 하락 청색) */
export const pctClass = (pct) => {
    if (pct === null || pct === undefined || !Number.isFinite(pct)) return 'flat';
    const r = Math.round(pct * 10) / 10;
    return r > 0 ? 'up' : r < 0 ? 'down' : 'flat';
};

/**
 * 등록 즉시 매도되는 설정인가. UP 은 현재가가 이미 지정가 이상, DOWN 은 이미 지정가 이하.
 * 현재가를 모르면 false (경고하지 않는다).
 */
export const firesImmediately = (trigger, price, cur) => {
    const p = num(price);
    const c = num(cur);
    if (p === null || c === null || p <= 0 || c <= 0) return false;
    return trigger === 'DOWN' ? c <= p : c >= p;
};

/**
 * 가격만 보고 방향을 제안한다. 기준은 현재가(없으면 매입가):
 * 현재가보다 낮은 가격은 손절(DOWN), 높은 가격은 익절(UP).
 * (현재가보다 낮은 UP 이나 높은 DOWN 은 등록 즉시 체결되므로 의도한 설정일 가능성이 낮다.)
 */
export const suggestTrigger = (price, cur, avg) => {
    const p = num(price);
    const ref = num(cur) > 0 ? num(cur) : num(avg);
    if (p === null || p <= 0 || !(ref > 0)) return 'UP';
    return p < ref ? 'DOWN' : 'UP';
};

/**
 * 폼 아래에 보여줄 안내.
 *   sentence : "5,120원 이하이면 매도 (매입가 대비 -7.9%)"
 *   warnings : 즉시 체결 / 방향과 가격이 어긋난 경우
 */
export const describeTier = ({ trigger, price, avg, cur }) => {
    const p = num(price);
    if (p === null || p <= 0) return { sentence: '', warnings: [] };
    const won = (v) => Number(v).toLocaleString();
    const pct = formatPct(pctVs(p, avg));
    const sentence = `${won(p)}원 ${TRIGGER_DESC[trigger]}${pct ? ` (매입가 대비 ${pct})` : ''}`;

    const warnings = [];
    if (firesImmediately(trigger, p, cur)) {
        warnings.push(`현재가(${won(cur)}원)가 이미 ${trigger === 'DOWN' ? '이하' : '이상'}이라 등록 즉시 매도됩니다.`);
    }
    return { sentence, warnings };
};
