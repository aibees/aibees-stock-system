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
                        <span class="label">{{ sm.menu_title || sm.menu_name }}</span>
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
import { ensureAccess } from '@scripts/useAccess.js';
import { assUserSession } from '@scripts/stores/user-stores.js';

const router    = useRouter();
const userStore = assUserSession();

/* ── 계정 ── */
const isLoggedIn  = computed(() => !!userStore.user.accessToken);
const userName    = computed(() => userStore.getUserInfo || '');
const userInitial = computed(() => (userName.value?.[0] ?? '?').toUpperCase());

/* ── 메뉴 ──
 * 권한(role_menu)이 반영된 트리를 쓴다. 서버(/master/menus/my)가 접근 가능한 메뉴만 내려주므로
 * 여기서 다시 거르지 않는다. */
const searchQuery = ref('');

const menuList = computed(() =>
    (userStore.user.menuList ?? [])
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
                sm.menu_title?.toLowerCase().includes(q) || sm.menu_name?.toLowerCase().includes(q))
        }))
        .filter(m => m.children.length > 0);
});

onMounted(() => ensureAccess());

// 최상위 경로는 '/stock' 처럼 선행 슬래시가 붙어 오고, 하위는 아닐 수 있어 항상 정규화해 이어 붙인다.
const joinPath = (parent, child) =>
    `/${String(parent ?? '').replace(/^\/+|\/+$/g, '')}/${String(child ?? '').replace(/^\/+|\/+$/g, '')}`;

const goTo = (path) => router.push({ path });

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
    route:   'M6 3v12M18 9v12M6 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM18 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
    dot:     'M12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4z',
};
const ICON_BY_CODE = {
    StockBuyTarget: 'star', StockInfo: 'list', ChartStock: 'chart', ChartTheme: 'chart', StockThemeDetail: 'list',
    WorldIndicators: 'globe',
    AutoTradeMode: 'sliders', TradeBuySetting: 'up', TradeSetting: 'down', AutoTradeLimit: 'clock',
    AutoTradeStatus: 'pulse', TradeSimulation: 'pulse',
    MyWallet: 'wallet', TradeProfit: 'coin', RecoPerformance: 'trophy', TradeLog: 'doc',
    BatchSetting: 'history', BatchLogSetting: 'doc', RouteList: 'route',
    RoleMenuSetting: 'shield', UserAuthSetting: 'user',
};
const iconOf = (code) => ICON[ICON_BY_CODE[code] ?? 'dot'];

// 하단 탭바에 같은 곳으로 가는 탭이 있는 메뉴는 그 탭 이름을 오른쪽에 작게 알려준다.
const NOTE = { StockBuyTarget: '종목', ChartStock: '차트' };
</script>

<style scoped lang="scss">
/* 양봉상회 전체 메뉴 v2 (목업 기준 토큰) */
$bg:     #FFFBEA;
$bar:    #FFF6D2;
$line:   #EFE2BC;
$line-2: #EAD9A6;
$ink:    #2B1D14;
$sub:    #7A6B5D;
$brown:  #7A4423;
$yellow: #F6C445;

#menu-page {
    min-height: 100vh;
    background: $bg;
    color: $ink;
    text-align: left;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
}

.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }

/* ── 헤더 ── */
.menu-header {
    position: sticky;
    top: env(safe-area-inset-top, 0px);   // 상태바 영역은 App.vue 의 고정 덮개가 가린다
    z-index: 50;
    background: $bar;
    border-bottom: 1px solid $line;
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;

    @media (min-width: 640px) { position: static; }
}

.account-row { display: flex; align-items: center; gap: 12px; min-height: 52px; }
.avatar {
    width: 44px;
    height: 44px;
    border-radius: 22px;
    background: $yellow;
    color: #3A200F;
    font-weight: 700;
    font-size: 17px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.who { flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: flex-start; gap: 1px; }
.who-name { font-size: 17px; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
.who-link {
    border: 0;
    background: transparent;
    padding: 0;
    min-height: 28px;
    font-size: 12px;
    color: $sub;
    cursor: pointer;
    font-family: inherit;
}

.search {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #fff;
    border: 1px solid $line-2;
    border-radius: 14px;
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
        &::-webkit-search-cancel-button { -webkit-appearance: none; }
    }
}

/* ── 본문 ── */
.menu-main {
    max-width: 640px;
    margin: 0 auto;
    padding: 16px 16px 24px;
    display: flex;
    flex-direction: column;
    gap: 18px;
}

.group {
    display: flex;
    flex-direction: column;
    gap: 8px;

    h2 { margin: 0 4px; font-size: 13px; font-weight: 600; color: $sub; }
}

.card {
    background: #fff;
    border: 1px solid $line;
    border-radius: 16px;
    overflow: hidden;
}

.item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 54px;
    padding: 0 14px;
    border: 0;
    border-bottom: 1px solid #F5EEDA;
    background: #fff;
    text-align: left;
    cursor: pointer;
    font-family: inherit;
    color: $ink;
    -webkit-tap-highlight-color: transparent;

    &:last-child { border-bottom: 0; }
    &:active { background: #FFFDF5; }

    .icon-box {
        width: 32px;
        height: 32px;
        border-radius: 10px;
        background: #FFF4CC;
        color: $brown;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    .label { flex: 1; min-width: 0; font-size: 15px; }
    .note { font-size: 12px; color: #A0662F; }
    .chev { color: #B8A890; flex-shrink: 0; }
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
</style>
