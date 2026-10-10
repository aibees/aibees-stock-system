/**
 * 매수타겟 종목 판정/표시 공용 로직 (홈 리스트 · 종목 상세 탭이 같이 쓴다).
 *
 * 입력은 /api/v1/stocks/buy-target 의 한 행(item). 새 필드를 만들지 않고 기존 필드만 쓴다.
 *   가격: open/high/low/close, volume, rate("9.37%")
 *   재무: per/pbr/roe/eps/peg
 *   기술 플래그: macd_cross('G'), obv_cross('G'), is_vol_limit/is_vol_surge/
 *               is_bb_mid_breakout/is_under_bb_upper/is_over_on_mid ('Y')
 *   chart_data: 최근 N영업일 [{date, open, high, low, close, ma20...}]
 */

export const numOrNull = (v) => {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
};

export const formatNumber = (v) => {
    const n = numOrNull(v);
    return n === null ? '-' : n.toLocaleString();
};

/* ── 재무 펀더멘털 판정 (일반적인 가치투자 기준선을 쓴 참고용 해석) ── */
export const fundamentalRows = (item) => {
    const per = numOrNull(item.per);
    const pbr = numOrNull(item.pbr);
    const roe = numOrNull(item.roe);
    const eps = numOrNull(item.eps);
    const peg = numOrNull(item.peg);

    return [
        {
            label: 'PER', value: per === null ? null : `${per}배`,
            pass: per === null ? null : (per > 0 && per <= 15),
            verdict: per === null ? '확인불가' : (per <= 0 ? '적자' : (per <= 15 ? '적합' : '높음')),
            desc: per === null ? '주가수익비율 정보가 없습니다.' : `주가수익비율 ${per}배 · 15배 이하를 저평가 참고 기준으로 봅니다.`,
        },
        {
            label: 'PBR', value: pbr === null ? null : `${pbr}배`,
            pass: pbr === null ? null : (pbr > 0 && pbr <= 1),
            verdict: pbr === null ? '확인불가' : (pbr <= 0 ? '확인불가' : (pbr <= 1 ? '적합' : '높음')),
            desc: pbr === null ? '주가순자산비율 정보가 없습니다.' : `주가순자산비율 ${pbr}배 · 1배 이하를 저평가 참고 기준으로 봅니다.`,
        },
        {
            label: 'ROE', value: roe === null ? null : `${roe}%`,
            pass: roe === null ? null : roe > 0,
            verdict: roe === null ? '확인불가' : (roe > 0 ? '적합' : '부적합'),
            desc: roe === null ? '자기자본이익률 정보가 없습니다.' : `자기자본이익률 ${roe} · ${roe > 0 ? '이익을 내고 있습니다.' : '손실 상태입니다.'}`,
        },
        {
            label: 'EPS', value: eps === null ? null : `${formatNumber(eps)}원`,
            pass: eps === null ? null : eps > 0,
            verdict: eps === null ? '확인불가' : (eps > 0 ? '적합' : '부적합'),
            desc: eps === null ? '주당순이익 정보가 없습니다.' : `주당순이익 ${formatNumber(eps)}원 · ${eps > 0 ? '흑자 기조입니다.' : '적자 상태입니다.'}`,
        },
        {
            label: 'PEG', value: peg === null ? null : `${peg}`,
            pass: peg === null ? null : (peg > 0 && peg <= 1),
            verdict: peg === null ? '확인불가' : (peg <= 0 ? '확인불가' : (peg <= 1 ? '적합' : '높음')),
            desc: peg === null ? '이익성장 대비 주가 정보가 없습니다.' : `PEG ${peg} · 1 이하를 이익성장 대비 저평가 참고 기준으로 봅니다.`,
        },
    ];
};

/* ── 기술적 근거 판정 (실제 지표 플래그를 그대로 쓰고 판정 문구만 서술형으로 변환)
 * 조건 정의는 strategy/kospi1.py, KisStockService.py 계산 로직을 따른다. ── */
export const technicalRows = (item) => [
    {
        label: 'MACD 크로스', short: 'MACD 골든크로스',
        pass: item.macd_cross === 'G',
        desc: item.macd_cross === 'G'
            ? '최근 며칠 내 MACD 선이 시그널선을 상향 돌파(골든크로스)했습니다.'
            : '최근 MACD 골든크로스가 발생하지 않았습니다.',
    },
    {
        label: 'OBV 크로스', short: 'OBV 돌파',
        pass: item.obv_cross === 'G',
        desc: item.obv_cross === 'G'
            ? '거래량 누적지표(OBV)가 최근 며칠 내 9일 이동평균을 상향 돌파했습니다.'
            : '거래량 누적지표(OBV)가 아직 9일 이동평균을 돌파하지 못했습니다.',
    },
    {
        label: '거래제한', short: '거래량 기준 충족',
        pass: item.is_vol_limit === 'Y',
        desc: item.is_vol_limit === 'Y'
            ? '오늘 거래량이 최소 거래량 기준선을 넘었습니다.'
            : '오늘 거래량이 최소 거래량 기준선에 못 미칩니다.',
    },
    {
        label: '거래급등', short: '거래량 급증',
        pass: item.is_vol_surge === 'Y',
        desc: item.is_vol_surge === 'Y'
            ? '최근 며칠 중 전일 대비 거래량이 급증한 날이 있었습니다.'
            : '최근 전일 대비 거래량 급증이 없었습니다.',
    },
    {
        label: 'BB중심돌파', short: '볼린저 중심선 돌파',
        pass: item.is_bb_mid_breakout === 'Y',
        desc: item.is_bb_mid_breakout === 'Y'
            ? '볼린저밴드 중심선 아래에 있다가 위로 돌파한 뒤 그 위에서 유지되고 있습니다.'
            : '볼린저밴드 중심선 돌파 후 유지 패턴이 확인되지 않았습니다.',
    },
    {
        label: 'BB상단아래', short: '과열 아님',
        pass: item.is_under_bb_upper === 'Y',
        desc: item.is_under_bb_upper === 'Y'
            ? '종가가 볼린저밴드 상단선 이하로, 단기 과열(추격 매수 구간)은 아닙니다.'
            : '종가가 볼린저밴드 상단선을 이미 넘어서 단기 과열 구간입니다.',
    },
    {
        label: '중심선위', short: '20일선 위',
        pass: item.is_over_on_mid === 'Y',
        desc: item.is_over_on_mid === 'Y'
            ? '종가가 20일 이동평균선 위에 있습니다.'
            : '종가가 20일 이동평균선 아래에 있습니다.',
    },
];

/** 충족한 기술 조건 수 / 전체 (조건 탭 헤더, 리스트 근거 한 줄) */
export const conditionCount = (item) => {
    const rows = technicalRows(item);
    return { pass: rows.filter(r => r.pass).length, total: rows.length };
};

/**
 * 리스트용 "근거 한 줄". 새 데이터를 만들지 않고 기존 기술 플래그에서 뽑는다.
 *  예) "조건 5/7 · MACD 골든크로스 · OBV 돌파"
 */
export const reasonLine = (item) => {
    const rows = technicalRows(item);
    const passed = rows.filter(r => r.pass).map(r => r.short);
    const { pass, total } = conditionCount(item);
    const head = passed.slice(0, 2).join(' · ');
    // 줄이 잘려도(말줄임) 핵심인 "조건 n/m" 이 보이도록 앞에 둔다.
    return head ? `조건 ${pass}/${total} · ${head}` : `조건 ${pass}/${total} 충족`;
};

/* ── 거래량 근거 수치 (chart_data 의 일별 volume 으로 계산, 새 필드 없음) ──
 * 기준선(최소 거래량)·급증 배수는 사용자 옵션(vol_limit / vol_surge, 기본 50만주·3배)이라
 * 화면에서는 기준값을 단정하지 않고 실제 수치만 보여준다.
 *   avgRatio : 기준일 거래량 / 직전 20영업일 평균
 *   surge    : 최근 5영업일 중 "전일 대비" 배수가 가장 큰 날 {date: 'MM/DD', ratio} */
const SURGE_LOOKBACK = 5;
const ratioText = (r) => `${r >= 10 ? Math.round(r).toLocaleString() : r.toFixed(1)}배`;
const AVG_WINDOW = 20;

export const volumeFacts = (item) => {
    const volume = numOrNull(item.volume);
    // 기준일 이후 봉이 섞이지 않게 기준일까지만 쓴다.
    const ymd = String(item.ymd || '');
    const rows = (item.chart_data || []).filter(r => String(r.date || '').slice(0, 10).replaceAll('-', '') <= ymd);
    const vols = rows.map(r => numOrNull(r.volume));

    let avgRatio = null;
    const past = vols.slice(-AVG_WINDOW - 1, -1).filter(v => v !== null && v > 0);
    const today = vols.length ? vols[vols.length - 1] : null;
    if (past.length >= 5 && today !== null) {
        avgRatio = today / (past.reduce((a, b) => a + b, 0) / past.length);
    }

    let surge = null;
    for (let i = Math.max(1, rows.length - SURGE_LOOKBACK); i < rows.length; i++) {
        const prev = vols[i - 1];
        const cur = vols[i];
        if (!prev || cur === null) continue;
        const ratio = cur / prev;
        if (!surge || ratio > surge.ratio) {
            const [, m, d] = String(rows[i].date).slice(0, 10).split('-');
            surge = { date: `${m}/${d}`, ratio };
        }
    }
    return { volume, avgRatio, surge };
};

/**
 * 펼친 추천 종목 안의 "조건 요약".
 *  - rows     : 7개 조건 한 줄씩 {label, pass, value}. 거래량 두 조건을 맨 앞에 두고 실제 수치를 값으로 쓴다.
 * (칩/뱃지 없이 "기호 · 라벨 — 값" 목록으로 그린다)
 */
export const conditionSummary = (item) => {
    const rows = technicalRows(item);
    const { pass, total } = conditionCount(item);
    const byLabel = Object.fromEntries(rows.map(r => [r.label, r]));
    const facts = volumeFacts(item);

    const limitValue = [
        facts.volume !== null ? `${formatNumber(facts.volume)}주` : null,
        facts.avgRatio !== null ? `평균 ${ratioText(facts.avgRatio)}` : null,
    ].filter(Boolean).join(' · ');
    const surgeValue = facts.surge ? `${facts.surge.date} 전일 대비 ${ratioText(facts.surge.ratio)}` : '';

    const VOLUME = { '거래제한': limitValue, '거래급등': surgeValue };
    const ordered = [byLabel['거래제한'], byLabel['거래급등'], ...rows.filter(r => !(r.label in VOLUME))];
    return {
        pass, total,
        rows: ordered.map(r => ({
            label: r.short,
            pass: r.pass,
            value: (r.label in VOLUME && VOLUME[r.label]) || (r.pass ? '충족' : '미충족'),
        })),
    };
};

/* ── 등락 ──
 * rate 는 "9.37%" 같은 문자열. 절대값(원)은 chart_data 의 전일 종가로 계산하고
 * (정확), 없으면 등락률로 역산한다(호가 단위 때문에 ±1~2원 오차 가능). */
export const parseRate = (rate) => {
    if (rate === null || rate === undefined || rate === '') return null;
    const n = parseFloat(String(rate).replace('%', ''));
    return Number.isNaN(n) ? null : n;
};

export const changeInfo = (item) => {
    const pct = parseRate(item.rate);
    const close = numOrNull(item.close);
    if (pct === null || close === null) return { dir: 0, abs: null, pct: null, text: '', cls: 'flat' };

    let abs = null;
    const rows = item.chart_data || [];
    if (rows.length >= 2) {
        const last = rows[rows.length - 1];
        const prev = rows[rows.length - 2];
        const sameDay = String(last.date || '').slice(0, 10).replaceAll('-', '') === String(item.ymd || '');
        const prevClose = numOrNull(prev.close);
        if (sameDay && prevClose !== null) abs = Math.abs(close - prevClose);
    }
    if (abs === null && pct !== 0) abs = Math.round(Math.abs(close - close / (1 + pct / 100)));

    const dir = pct > 0 ? 1 : (pct < 0 ? -1 : 0);
    const mark = dir > 0 ? '▲' : (dir < 0 ? '▼' : '–');
    const pctText = `${dir > 0 ? '+' : (dir < 0 ? '−' : '')}${Math.abs(pct).toFixed(2)}%`;
    const absText = abs !== null && dir !== 0 ? ` ${abs.toLocaleString()}` : '';
    return {
        dir, abs, pct,
        text: `${mark}${absText} ${pctText}`.trim(),   // 예) "▲ 2,000 +2.44%"
        cls: dir > 0 ? 'up' : (dir < 0 ? 'down' : 'flat'),
    };
};

/** 저가~고가 트랙 위의 위치(0~100%). 고가=저가면 가운데. */
export const rangePos = (item, value) => {
    const low = numOrNull(item.low);
    const high = numOrNull(item.high);
    const v = numOrNull(value);
    if (low === null || high === null || v === null) return null;
    if (high === low) return 50;
    return Math.min(100, Math.max(0, ((v - low) / (high - low)) * 100));
};

export const hasValue = (v) => numOrNull(v) !== null;

/* ── 장 상태 (KST) ──
 * 정규장 평일 09:00~15:30. ※ 공휴일/임시휴장은 반영하지 않는다(TODO: 휴장일 API 가 생기면 연동). */
const WEEKDAY_KO = ['일', '월', '화', '수', '목', '금', '토'];

export const kstNowParts = (date = new Date()) => {
    const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hour12: false, weekday: 'short',
    }).formatToParts(date);
    const get = (t) => parts.find(p => p.type === t)?.value;
    const WD = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
    return {
        year: Number(get('year')), month: Number(get('month')), day: Number(get('day')),
        hour: Number(get('hour')) % 24, minute: Number(get('minute')), weekday: WD[get('weekday')],
    };
};

export const isMarketOpenNow = (kst) => {
    if (kst.weekday === 0 || kst.weekday === 6) return false;
    const m = kst.hour * 60 + kst.minute;
    return m >= 9 * 60 && m < 15 * 60 + 30;
};

export const weekdayKo = (ymdDash) => {
    const [y, m, d] = ymdDash.split('-').map(Number);
    return WEEKDAY_KO[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
};

/* ── 날짜 헬퍼 (홈 · 상세 공용) ── */
export const toYmdString = (y, m, d) => `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;

export const shiftDate = (y, m, d, deltaDays) => {
    const dt = new Date(Date.UTC(y, m - 1, d));
    dt.setUTCDate(dt.getUTCDate() + deltaDays);
    return { year: dt.getUTCFullYear(), month: dt.getUTCMonth() + 1, day: dt.getUTCDate(), weekday: dt.getUTCDay() };
};

/**
 * 매수타겟 기준일 기본값: 가장 최신 배치 데이터가 있는 날 (KST).
 * - 배치는 평일 20:00 에 완료된다. 평일 20시 이후면 오늘, 그 전이거나 주말이면 직전 영업일.
 */
export const getLatestBatchDate = () => {
    const kst = kstNowParts();
    const isWeekend = kst.weekday === 0 || kst.weekday === 6;
    if (!isWeekend && kst.hour >= 20) return toYmdString(kst.year, kst.month, kst.day);

    let d = shiftDate(kst.year, kst.month, kst.day, -1);
    while (d.weekday === 0 || d.weekday === 6) d = shiftDate(d.year, d.month, d.day, -1);
    return toYmdString(d.year, d.month, d.day);
};

/**
 * 기준일(YYYY-MM-DD)의 장 상태 라벨.
 * 장중(오늘 + 정규장)이면 "장중 · HH:mm 기준" — '종가'라는 말은 쓰지 않는다(현재가와 같은 값이라 오해를 부른다).
 * 그 외는 "종가 · MM/DD 마감".
 */
export const marketStatus = (ymdDash, kst) => {
    const today = toYmdString(kst.year, kst.month, kst.day);
    if (ymdDash === today && isMarketOpenNow(kst)) {
        return { state: 'live', label: `장중 · ${String(kst.hour).padStart(2, '0')}:${String(kst.minute).padStart(2, '0')} 기준` };
    }
    const [, m, d] = ymdDash.split('-');
    return { state: 'closed', label: `종가 · ${m}/${d} 마감` };
};
