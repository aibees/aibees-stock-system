// ──────────────────────────────────────────────────────────────────────────
// 비밀상회 테마 (회의록 2026-11-17 「비밀상회 디자인 분리」 3장 3·4·10·11)
//
//  - 전환: <html data-theme="..."> 속성만 바꾼다. 색은 sass/theme.css 의 CSS 변수라 리렌더가 필요 없다.
//  - 저장: Capacitor Preferences(네이티브) — iOS 웹뷰는 localStorage 가 지워지는 경우가 있다.
//          localStorage 에도 같이 적어 두는데, 이건 index.html 의 첫 페인트용(동기 읽기) 사본일 뿐이다.
//  - 상태바: 네이티브에서는 StatusBar 플러그인으로 글자색(밝음/어두움)과 배경을 테마에 맞춘다.
//  - 차트: Chart.js / lightweight-charts 옵션은 JS 값이라 CSS 변수를 따라오지 않는다.
//          onThemeChange() 로 구독해서 옵션을 다시 넣는다. 색은 themeColor('--sc-text') 로 읽는다.
//
// 아이콘·스플래시는 빌드 타임 고정이라 테마를 따라가지 않는다(구분 책임은 로고가 진다).
// ──────────────────────────────────────────────────────────────────────────
import { Capacitor } from '@capacitor/core';
import { onBeforeUnmount, ref } from 'vue';

export const THEMES = [
    { id: 'dark-teal',    label: '다크 틸',      desc: '어두운 바탕 + 틸 포인트', dark: true,  swatch: ['#0E0F12', '#16181D', '#2DD4BF'] },
    { id: 'light-violet', label: '라이트 바이올렛', desc: '밝은 무채색 + 바이올렛',   dark: false, swatch: ['#FAFAFA', '#FFFFFF', '#6D5BD0'] },
    { id: 'light-rose',   label: '라이트 로즈',   desc: '연분홍 바탕 + 딥로즈',    dark: false, swatch: ['#FDF2F7', '#FFFFFF', '#D4537E'] },
];
export const DEFAULT_THEME = 'dark-teal';

const STORAGE_KEY = 'sc-theme';
const isValid = (id) => THEMES.some((t) => t.id === id);
const listeners = new Set();
let current = DEFAULT_THEME;
// 테마가 바뀔 때마다 1씩 오른다. computed 안에서 읽어 두면 테마 전환 시 색 계산이 다시 돈다
// (SVG 속성처럼 var() 를 못 쓰는 곳용).
export const themeVersion = ref(0);

const readLocal = () => {
    try { return localStorage.getItem(STORAGE_KEY); } catch { return null; }
};
const writeLocal = (id) => {
    try { localStorage.setItem(STORAGE_KEY, id); } catch { /* 사파리 개인정보 보호 모드 등 */ }
};

const loadPreferences = async () => {
    if (!Capacitor.isNativePlatform()) return null;
    try {
        const { Preferences } = await import('@capacitor/preferences');
        const { value } = await Preferences.get({ key: STORAGE_KEY });
        return value;
    } catch { return null; }
};
const savePreferences = async (id) => {
    if (!Capacitor.isNativePlatform()) return;
    try {
        const { Preferences } = await import('@capacitor/preferences');
        await Preferences.set({ key: STORAGE_KEY, value: id });
    } catch { /* 저장 실패해도 현재 화면 테마는 이미 바뀌었다 */ }
};

// CSS 변수 값 읽기(차트 등 JS 쪽에서 쓰는 색). 테마 적용 직후에도 정확하다(동기 스타일 계산).
export const themeColor = (name, fallback = '') => {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
};

// '#RRGGBB' + 투명도 → 'rgba(r,g,b,a)'. 차트 라이브러리는 color-mix() 를 못 읽는다.
export const alpha = (hex, a) => {
    const h = String(hex).replace('#', '');
    if (!/^[0-9a-fA-F]{6}$/.test(h)) return hex;
    const n = parseInt(h, 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
};

// 차트에서 자주 쓰는 색 묶음(호출 시점의 테마 기준).
export const chartPalette = () => ({
    up:       themeColor('--sc-up', '#E24B4A'),
    down:     themeColor('--sc-down', '#378ADD'),
    flat:     themeColor('--sc-text-mute', '#646A75'),
    bg:       themeColor('--sc-surface', '#16181D'),
    text:     themeColor('--sc-text', '#E7E9EE'),
    textSub:  themeColor('--sc-text-sub', '#8B919C'),
    grid:     themeColor('--sc-border', '#2A2D34'),
    line:     themeColor('--sc-border-strong', '#3A3E47'),
    point:    themeColor('--sc-point', '#2DD4BF'),
    strongBg: themeColor('--sc-strong-bg', '#23262D'),
});

const syncStatusBar = async (id) => {
    if (!Capacitor.isNativePlatform()) return;
    try {
        const { StatusBar, Style } = await import('@capacitor/status-bar');
        const dark = THEMES.find((t) => t.id === id)?.dark ?? true;
        // Style.Dark = 밝은 글자(어두운 배경용), Style.Light = 어두운 글자(밝은 배경용)
        await StatusBar.setStyle({ style: dark ? Style.Dark : Style.Light });
        if (Capacitor.getPlatform() === 'android') {
            await StatusBar.setBackgroundColor({ color: themeColor('--sc-surface', '#16181D') });
        }
    } catch { /* 플러그인 미설치(구 빌드) — 상태바만 기본값 */ }
};

const syncMetaThemeColor = () => {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', themeColor('--sc-surface', '#16181D'));
};

const apply = (id) => {
    current = id;
    document.documentElement.setAttribute('data-theme', id);
    themeVersion.value++;
    syncMetaThemeColor();
    syncStatusBar(id);
    listeners.forEach((fn) => { try { fn(id); } catch (e) { console.error('[theme] listener', e); } });
};

export const getTheme = () => current;

export const setTheme = async (id) => {
    if (!isValid(id)) id = DEFAULT_THEME;
    apply(id);
    writeLocal(id);
    await savePreferences(id);
};

// 앱 시작 시 1회. localStorage 사본으로 즉시 적용하고, 네이티브면 Preferences 값으로 보정한다.
export const initTheme = () => {
    const local = readLocal();
    apply(isValid(local) ? local : DEFAULT_THEME);
    loadPreferences().then((saved) => {
        if (isValid(saved) && saved !== current) {
            apply(saved);
            writeLocal(saved);
        } else if (!saved && isValid(local)) {
            savePreferences(local);   // 예전 빌드에서 넘어온 경우 Preferences 로 옮겨 둔다
        }
    });
};

// 테마 바뀔 때 콜백. 반환값을 호출하면 구독 해제. 컴포넌트에서는 useThemeChange() 를 쓴다.
export const onThemeChange = (fn) => {
    listeners.add(fn);
    return () => listeners.delete(fn);
};

// 컴포넌트용: 마운트된 동안만 구독한다.
export const useThemeChange = (fn) => {
    const off = onThemeChange(fn);
    onBeforeUnmount(off);
};

// Chart.js 전역 기본색(축 글자·격자)을 테마에 맞춘다. Chart.register 하는 곳에서 한 번씩 불러도 된다(중복 무시).
// 테마가 바뀌면 기본색을 다시 넣고 떠 있는 차트를 모두 update() — 옵션을 다시 해석하면서 새 기본값을 읽는다.
let chartJsHooked = false;
export const setupChartJsTheme = (Chart) => {
    const applyDefaults = () => {
        const p = chartPalette();
        Chart.defaults.color = p.textSub;
        Chart.defaults.borderColor = p.grid;
    };
    applyDefaults();
    if (chartJsHooked) return;
    chartJsHooked = true;
    onThemeChange(() => {
        applyDefaults();
        Object.values(Chart.instances || {}).forEach((c) => { try { c.update('none'); } catch { /* 파괴 중인 차트 */ } });
    });
};
