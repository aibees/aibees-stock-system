<template>
    <div id="menu-page">

        <!-- ════════ 헤더(v2): 계정 + 메뉴 검색. 모바일에서는 sticky(+세이프 에어리어) ════════ -->
        <header class="menu-header" data-ad-anchor>
            <div class="account-row">
                <span class="avatar" aria-hidden="true">{{ isLoggedIn ? userInitial : '?' }}</span>
                <div class="who">
                    <template v-if="isLoggedIn">
                        <span class="who-name">{{ userName }} 님</span>
                        <button type="button" class="who-link" @click="goTo('/user-option')">계정 설정 ›</button>
                    </template>
                    <template v-else>
                        <span class="who-name">로그인이 필요해요</span>
                        <button type="button" class="who-link" @click="goTo('/login')">로그인 ›</button>
                    </template>
                </div>
            </div>

            <label class="search">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
                <span class="sr-only">메뉴 검색</span>
                <input v-model="searchQuery" type="search" placeholder="메뉴 검색" autocomplete="off" />
            </label>
        </header>

        <!-- 꿀 지갑(로그인했을 때) -->
        <section v-if="isLoggedIn && honey.available" class="wallet" aria-label="내 꿀">
            <button type="button" class="w-top" @click="goTo(HONEY_HISTORY_PATH)"><span><img src="/img/emoji/honey.png" alt="" /> 내 꿀</span><span class="w-more">내역 ›</span></button>
            <p class="w-bal">{{ honey.balance.toLocaleString() }}<span>꿀</span></p>
            <p class="w-hint">{{ honey.allDone ? '오늘 꿀을 다 모았어요' : `오늘 ${honey.todayLeft.toLocaleString()}꿀 더 모을 수 있어요` }}</p>
            <button type="button" class="w-btn" @click="goTo(HONEY_PATH)">꿀 모으기</button>
        </section>

        <main class="menu-main">
            <!-- 그룹 = 최상위 메뉴, 항목 = 하위 메뉴. 권한이 없는 메뉴는 서버가 내려주지 않아 나오지 않는다. -->
            <section v-for="m in filteredMenuList" :key="m.menu_code" class="group">
                <h2>{{ m.menu_title || m.menu_name }}</h2>
                <div class="card">
                    <button v-for="sm in m.children" :key="sm.menu_code" type="button" class="item"
                        @click="goTo(joinPath(m.menu_path, sm.menu_path))">
                        <span class="icon-box" aria-hidden="true">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path :d="iconOf(sm.menu_code)"></path></svg>
                        </span>
                        <span class="label">{{ menuLabel(sm) }}</span>
                        <span v-if="NOTE[sm.menu_code]" class="note">{{ NOTE[sm.menu_code] }}</span>
                        <svg class="chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="m9 6 6 6-6 6"></path></svg>
                    </button>
                </div>
            </section>

            <p v-if="!filteredMenuList.length" class="empty">{{ searchQuery ? '검색 결과가 없어요.' : '이용할 수 있는 메뉴가 없어요.' }}</p>

            <button v-if="isLoggedIn" type="button" class="logout" @click="handleLogout">로그아웃</button>
        </main>
    </div>
</template>

<script setup>
import { menuLabel } from '@scripts/menuLabel.js';
import { useHoneyStore } from '@scripts/stores/honey-store.js';
import { HONEY_PATH, HONEY_HISTORY_PATH } from '@scripts/support.js';
import { ensureAccess } from '@scripts/useAccess.js';
import { assUserSession } from '@scripts/stores/user-stores.js';
import { chapters } from '@scripts/training.js';
import { requireStockNotice } from '@scripts/stockNotice.js';

const router    = useRouter();
const userStore = assUserSession();

/* ── 계정 ── */
const isLoggedIn  = computed(() => !!userStore.user.accessToken);
const honey = useHoneyStore();
onMounted(() => { if (isLoggedIn.value) honey.load(); });
const userName    = computed(() => userStore.getUserInfo || '');
const userInitial = computed(() => (userName.value?.[0] ?? '?').toUpperCase());

/* ── 메뉴 ──
 * 권한(role_menu)이 반영된 트리를 쓴다. 서버(/master/menus/my)가 접근 가능한 메뉴만 내려주므로
 * 여기서 다시 거르지 않는다. */
const searchQuery = ref('');

// 트레이닝은 정적 화면이라 서버 메뉴와 무관하게 맨 위에 둔다. 항목은 장(chapter) — 누르면 목차의 그 장으로 간다
// (/training/<장>, 장·단계 목록은 scripts/training.js).
const trainingGroup = {
    menu_code: 'TrainingGroup', menu_name: '트레이닝', menu_title: '트레이닝', display_flag: 'Y',
    menu_path: 'training',
    children: chapters().map(ch => ({
        menu_code: `Training_${ch.slug}`, menu_path: ch.slug, display_flag: 'Y',
        menu_name: ch.name, menu_title: ch.name,
    })).concat({
        menu_code: 'TrainingQuiz', menu_path: 'quiz', display_flag: 'Y',
        menu_name: '퀴즈', menu_title: '퀴즈',
    }, {
        menu_code: 'TrainingGlossary', menu_path: 'glossary', display_flag: 'Y',
        menu_name: '주식 용어 사전', menu_title: '주식 용어 사전',
    }),
};
// 내 설정(preset)은 주식분석 그룹의 정적 화면 — 서버 메뉴에 그 그룹이 있으면 그 끝에 붙이고, 없으면 혼자 한 그룹으로 둔다.
// 고객지원 묶음. 하위 경로가 '/'로 시작하면 그 경로로 바로 간다(joinPath).
const supportGroup = computed(() => ({
    menu_code: 'SupportGroup', menu_path: 'support', menu_name: '고객지원', menu_title: '고객지원', display_flag: 'Y',
    children: [
        { menu_code: 'SupportFaq', menu_path: 'faq', menu_name: '자주 묻는 질문', menu_title: '자주 묻는 질문', display_flag: 'Y' },
        { menu_code: 'SupportContact', menu_path: 'contact', menu_name: '문의하기', menu_title: '문의하기', display_flag: 'Y' },
        { menu_code: 'SupportTerms', menu_path: 'terms', menu_name: '이용약관', menu_title: '이용약관', display_flag: 'Y' },
        { menu_code: 'SupportPrivacy', menu_path: 'privacy', menu_name: '개인정보 처리방침', menu_title: '개인정보 처리방침', display_flag: 'Y' },
        { menu_code: 'SupportLicenses', menu_path: 'licenses', menu_name: '오픈소스 라이선스', menu_title: '오픈소스 라이선스', display_flag: 'Y' },
        ...(isLoggedIn.value ? [{ menu_code: 'SupportAccount', menu_path: '/user-option', menu_name: '계정 설정', menu_title: '계정 설정', display_flag: 'Y' }] : []),
    ],
}));
const presetItem = { menu_code: 'StockPreset', menu_path: 'preset', display_flag: 'Y', menu_name: '내 설정', menu_title: '내 설정' };
const withPreset = (menus) => {
    const isStock = (m) => String(m.menu_path ?? '').replace(/^\/+|\/+$/g, '') === 'stock';
    if (menus.some(isStock)) {
        return menus.map(m => (isStock(m) && !(m.children ?? []).some(c => c.menu_code === 'StockPreset')
            ? { ...m, children: [...(m.children ?? []), presetItem] } : m));
    }
    return [...menus, { menu_code: 'StockGroup', menu_path: 'stock', display_flag: 'Y', menu_name: '주식분석', menu_title: '주식분석', children: [presetItem] }];
};
const menuList = computed(() =>
    [...withPreset([trainingGroup, ...(userStore.user.menuList ?? [])]), supportGroup.value]
        .filter(m => m.display_flag === 'Y')
        .map(m => ({ ...m, children: (m.children ?? []).filter(sm => sm.display_flag === 'Y') }))
        .filter(m => m.children.length > 0)
);

const filteredMenuList = computed(() => {
    const q = searchQuery.value.trim().toLowerCase();
    if (!q) return menuList.value;
    return menuList.value
        .map(m => ({
            ...m,
            children: m.children.filter(sm =>
                menuLabel(sm).toLowerCase().includes(q) || sm.menu_title?.toLowerCase().includes(q) || sm.menu_name?.toLowerCase().includes(q))
        }))
        .filter(m => m.children.length > 0);
});

onMounted(() => ensureAccess());

// 최상위 경로는 '/stock' 처럼 선행 슬래시가 붙어 오고, 하위는 아닐 수 있어 항상 정규화해 이어 붙인다.
const joinPath = (parent, child) => String(child ?? '').startsWith('/') ? child :
    `/${String(parent ?? '').replace(/^\/+|\/+$/g, '')}/${String(child ?? '').replace(/^\/+|\/+$/g, '')}`;

// 주식분석(/stock 아래) 항목은 탭바와 같이, 유의사항에 동의하기 전이면 팝업부터 띄운다(scripts/stockNotice.js).
const goTo = (path) => {
    if (/^\/stock(\/|$)/.test(path) && !requireStockNotice(path)) return;
    router.push({ path });
};

const handleLogout = () => {
    userStore.logoutUser();
    router.push({ path: '/login' });
};

/* ── 아이콘 / 바로가기 표시 ──
 * 메뉴 코드별 아이콘(24×24, 선 아이콘). 매핑에 없는 메뉴는 기본 점 아이콘. */
const ICON = {
    star:    'm12 3 2.7 5.6 6.1.8-4.5 4.2 1.1 6L12 16.7 6.6 19.6l1.1-6-4.5-4.2 6.1-.8z',
    list:    'M4 6h16M4 12h16M4 18h10',
    chart:   'M3 17l5-5 4 3 8-8M15 7h5v5',
    globe:   'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c2.5 3 2.5 15 0 18M12 3c-2.5 3-2.5 15 0 18',
    sliders: 'M4 7h10M18 7h2M4 17h4M12 17h8M14 5v4M8 15v4',
    up:      'M12 19V5M6 11l6-6 6 6',
    down:    'M12 5v14M6 13l6 6 6-6',
    clock:   'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2',
    pulse:   'M3 12h4l2-6 4 12 2-6h6',
    wallet:  'M3 7h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM3 7l12-3v3M16 13h2',
    coin:    'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM9 9.5c0-1 1.3-1.8 3-1.8s3 .8 3 1.8-1.3 1.6-3 2-3 1-3 2 1.3 1.8 3 1.8 3-.8 3-1.8M12 6v1.7M12 16.3V18',
    trophy:  'M7 4h10v4a5 5 0 0 1-10 0zM7 6H4a3 3 0 0 0 3 3M17 6h3a3 3 0 0 1-3 3M12 13v4M8 20h8',
    doc:     'M6 3h9l4 4v14H6zM9 11h6M9 15h6M9 7h3',
    history: 'M12 8v4l3 2M3 12a9 9 0 1 0 3-6.7M3 4v5h5',
    shield:  'M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z',
    user:    'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-4 3.6-6 8-6s8 2 8 6',
    key:     'M8 15a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM11 11h10M17 11v3M20 11v2',
    route:   'M6 3v12M18 9v12M6 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM18 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
    grid:    'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z',
    target:  'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
    book:    'M5 4.5A2.5 2.5 0 0 1 7.5 2H19v17H7.5A2.5 2.5 0 0 0 5 21.5zM5 19.5v-15M9 7h6M9 11h6',
    dot:     'M12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4z',
    help:    'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17.5v.01',
    mail:    'M3 6h18v12H3zM3 7l9 6 9-6',
    bell:    'M6 16V11a6 6 0 1 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0',
};
const ICON_BY_CODE = {
    TrainingGlossary: 'book', TrainingQuiz: 'target',
    SupportFaq: 'help', SupportContact: 'mail', SupportTerms: 'doc', SupportPrivacy: 'shield', SupportLicenses: 'book', SupportAccount: 'user',
    StockBuyTarget: 'star', StockPreset: 'sliders', StockInfo: 'list', StockSector: 'grid', ChartStock: 'chart', ChartTheme: 'chart', StockThemeDetail: 'list',
    WorldIndicators: 'globe',
    BatchSetting: 'history', BatchLogSetting: 'doc', RouteList: 'route',
    RoleMenuSetting: 'shield', UserAuthSetting: 'user', MasterInfoSetting: 'key',
};
const iconOf = (code) => ICON[ICON_BY_CODE[code] ?? (String(code).startsWith('Training_') ? 'doc' : 'dot')];

// 하단 탭바에 같은 곳으로 가는 탭이 있는 메뉴는 그 탭 이름을 오른쪽에 작게 알려준다.
const NOTE = {};
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

/* 양봉상회 전체 메뉴 — 2026-11-17 화이트 톤 개편.
 * 그룹 = 흰 판, 그룹 사이 = 연회색 띠. 항목 사이 선 없이 높이로 나눈다(메뉴 행: 아이콘 · 이름 · ›). */
#menu-page {
    min-height: 100vh;
    background: $band;
    color: $ink;
    text-align: left;
    font-family: $font-body;
    letter-spacing: -0.2px;
    -webkit-font-smoothing: antialiased;
}

.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }

/* ── 헤더 ── */
.menu-header {
    position: sticky;
    top: env(safe-area-inset-top, 0px);   // 상태바 영역은 App.vue 의 고정 덮개가 가린다
    z-index: 50;
    background: $card;
    padding: 12px $pad-x 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;

    @media (min-width: 640px) { position: static; }
}

.account-row { display: flex; align-items: center; gap: 12px; min-height: 56px; }
.avatar {
    width: 44px;
    height: 44px;
    border-radius: 22px;
    background: $honey-100;
    color: $amber-700;
    font-weight: 700;
    font-size: 17px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.who { flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: flex-start; gap: 2px; }
.who-name { font-size: 18px; font-weight: 700; letter-spacing: -0.4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
.who-link {
    border: 0;
    background: transparent;
    padding: 0;
    min-height: 24px;
    font-size: 13px;
    color: $sub;
    cursor: pointer;
    font-family: inherit;
}

.search {
    display: flex;
    align-items: center;
    gap: 8px;
    background: $band;
    border-radius: 12px;
    padding: 0 14px;
    min-height: 44px;
    color: $sub;

    input {
        flex: 1;
        min-width: 0;
        border: 0;
        outline: none;
        background: transparent;
        font-size: 15px;
        font-family: inherit;
        color: $ink;
        -webkit-appearance: none;
        appearance: none;
        &::placeholder { color: $sub; }
        &::-webkit-search-cancel-button { -webkit-appearance: none; }
    }
}

/* ── 본문 ── */
.menu-main {
    max-width: 640px;
    margin: 0 auto;
    padding: $band-h 0 24px;
    display: flex;
    flex-direction: column;
    gap: $band-h;
}

.group {
    background: $card;
    padding: 20px 0 8px;
    display: flex;
    flex-direction: column;

    h2 { margin: 0 $pad-x 4px; font-size: 14px; font-weight: 600; color: $sub; }
}

.card { background: transparent; }

.item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 14px;
    min-height: 56px;
    padding: 0 $pad-x;
    border: 0;
    background: transparent;
    text-align: left;
    cursor: pointer;
    font-family: inherit;
    color: $ink;
    -webkit-tap-highlight-color: transparent;

    &:active { background: $honey-50; }

    .icon-box {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        background: $honey-50;
        color: $amber-700;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    .label { flex: 1; min-width: 0; font-size: 16px; }
    .note { font-size: 12px; color: $sub; }
    .chev { color: $sub-2; flex-shrink: 0; }
}

.empty { margin: 24px 0; text-align: center; font-size: 14px; color: $sub; }

.logout {
    align-self: center;
    border: 0;
    background: transparent;
    min-height: 44px;
    padding: 0 16px;
    font-size: 14px;
    color: $sub;
    cursor: pointer;
    font-family: inherit;
}

/* 2026-11-17 꿀빛 톤: 아바타·메뉴 아이콘 칸 꿀색 */
.who-link { color: $amber-700; font-weight: 600; }

/* ── 꿀 지갑 ── */
.wallet { margin: 4px 20px 8px; padding: 16px 18px; border-radius: 14px; background: #FFF8E8; border: 1px solid #FFEBC2; text-align: left; }
.wallet .w-top { width: 100%; display: flex; justify-content: space-between; align-items: center; padding: 0; border: 0; background: transparent; font: inherit; font-size: 13px; font-weight: 700; color: #B76E00; cursor: pointer; img { width: 20px; height: 20px; vertical-align: -5px; } }
.wallet .w-bal { margin: 6px 0 0; font-size: 28px; font-weight: 800; letter-spacing: -.7px; color: #4A2F00; span { font-size: 16px; margin-left: 2px; } }
.wallet .w-hint { margin: 2px 0 12px; font-size: 13px; color: #7A5A1E; }
.wallet .w-btn { width: 100%; height: 44px; border: 0; border-radius: 10px; background: #5A3C08; color: #fff; font: inherit; font-size: 14.5px; font-weight: 700; cursor: pointer; }
@media (min-width: 900px) { .wallet { max-width: 640px; margin-left: auto; margin-right: auto; } }

/* ══ 2026-11-22 간격 통일(8px 격자, 토큰: _home-tokens.scss — 홈과 같은 규칙) — 위의 값보다 이 블록이 우선 ══
   섹션 위 24 · 제목→내용 12 · 카드 안쪽 16 · 카드·요소 사이 12 · 한 줄 56
   메뉴 그룹 이름(회색 작은 글씨)은 목록과 한 덩어리라 8 */
.menu-header { padding: $card-pad $pad-x; }
.search { padding: 0 $card-pad; }
.menu-main { padding-bottom: $sec-pb; }
.group { padding: $sec-pt 0 $gap; h2 { margin-bottom: 8px; } }
.item { gap: $gap; }
.wallet { margin: $gap $pad-x; padding: $card-pad; }
.wallet .w-hint { margin-bottom: $gap; }
.empty { margin: $sec-pt 0; }
</style>
