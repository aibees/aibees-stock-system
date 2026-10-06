<template>
    <!-- ── Web: 상단 글로벌 내비게이션 ── -->
    <nav id="comm-lnb-web">
        <div class="lnb-web-inner">
            <div class="lnb-brand" @click="goPath('/home')">
                <!-- 브랜드 마크: public/favicon.svg (벌집 > 꿀단지 > 양봉 3개) -->
                <img class="lnb-logo" src="/favicon.svg" alt="" aria-hidden="true" />
                <span>양봉상회</span>
            </div>

            <ul class="lnb-menu">
                <li v-for="m in topMenus" :key="m.menu_code" class="lnb-item"
                    :class="{ active: isActiveTop(m), 'has-children': hasChildren(m) }"
                    @mouseenter="openCode = m.menu_code" @mouseleave="openCode = ''"
                    @click="onTopClick(m)">
                    <span class="lnb-item-label">
                        {{ m.menu_title || m.menu_name }}
                        <span v-if="hasChildren(m)" class="caret" :class="{ open: openCode === m.menu_code }"></span>
                    </span>

                    <transition name="drop">
                        <ul v-if="hasChildren(m) && openCode === m.menu_code" class="lnb-dropdown">
                            <li v-for="c in visibleChildren(m)" :key="c.menu_code"
                                :class="{ active: isActiveChild(m, c) }" @click.stop="goChild(m, c)">
                                {{ c.menu_title || c.menu_name }}
                            </li>
                        </ul>
                    </transition>
                </li>
            </ul>
        </div>
    </nav>

    <!-- ── Mobile: 하단 탭 바 (홈 / 종목 / 차트 / 매매 기록) ──
         권한이 없는 탭은 그리지 않는다(access.paths — 서버가 내려준 접근 가능 경로). -->
    <nav id="comm-lnb" aria-label="주요 메뉴">
        <a v-for="t in visibleTabs" :key="t.key" class="tab" :class="{ active: isTabActive(t) }"
            :href="t.path" :aria-current="isTabActive(t) ? 'page' : undefined" @click.prevent="goPath(t.path)">
            <svg v-if="t.key === 'home'" width="24" height="24" viewBox="0 0 24 24" :fill="isTabActive(t) ? '#FFC20E' : 'none'" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"></path></svg>
            <svg v-else-if="t.key === 'stocks'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h10"></path></svg>
            <svg v-else-if="t.key === 'chart'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 17l5-5 4 3 8-8"></path><path d="M15 7h5v5"></path></svg>
            <svg v-else width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="3" width="14" height="18" rx="2"></rect><path d="M9 8h6M9 12h6M9 16h3" stroke-linecap="round"></path></svg>
            <span class="tab-label">{{ t.label }}</span>
        </a>
    </nav>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { assUserSession } from "../../scripts/stores/user-stores";

const router = useRouter();
const route = useRoute();
const userSession = assUserSession();

/* ── 하단 탭바 ── */
const TABS = [
    { key: 'home',   label: '홈',      path: '/home',              match: ['/home'] },
    { key: 'stocks', label: '종목',    path: '/stock/buy-target',  match: ['/stock/buy-target', '/stock/info'] },
    { key: 'chart',  label: '차트',    path: '/stock/chart',       match: ['/stock/chart'] },
    { key: 'log',    label: '매매 기록', path: '/trade/trade-log',   match: ['/trade/trade-log'] },
];
// 홈은 항상, 나머지는 서버가 이 사용자에게 허용한 경로(access.paths)에 있을 때만 보인다.
const visibleTabs = computed(() =>
    TABS.filter(t => t.key === 'home' || userSession.access.paths.includes(t.path)));
const isTabActive = (t) => t.match.some(p => route.path === p || route.path.startsWith(p + '/'));

const isUser = ref(false);
const userName = ref('');
// 권한 반영본 메뉴(스토어). 로그인/로그아웃으로 바뀌면 자동 반영되도록 computed 로 읽는다.
const allMenu = computed(() => userSession.user.menuList ?? []);
const openCode = ref('');

// 메뉴 권한은 서버(/master/menus/my → role_menu)가 걸러서 내려준 menuList 를 그대로 쓴다.

/* ── 노출 가능한 최상위 메뉴 (표시/사용/권한 필터 + 정렬) ── */
const topMenus = computed(() => {
    return (allMenu.value ?? [])
        .filter(m => m.display_flag !== 'N' && m.enabled_flag !== 'N')
        .sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0));
});

const visibleChildren = (m) => {
    return (m.children ?? [])
        .filter(c => c.display_flag !== 'N' && c.enabled_flag !== 'N')
        .sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0));
};

const hasChildren = (m) => visibleChildren(m).length > 0;

/* ── 활성 메뉴 판별 ── */
const currentTop = computed(() => route.path.split('/').filter(p => p !== '')[0] ?? '');

const isActiveTop = (m) => currentTop.value === m.menu_path;

const isActiveChild = (m, c) => route.path === `/${m.menu_path}/${c.menu_path}`;

/* ── 이동 ── */
const goPath = (path) => {
    router.push({ path });
};

const goChild = (m, c) => {
    openCode.value = '';
    router.push({ path: `${m.menu_path}/${c.menu_path}` });
};

const onTopClick = (m) => {
    const children = visibleChildren(m);
    if (children.length > 0) {
        // 자식이 있으면 첫번째 자식으로 이동 (드롭다운은 hover로 노출)
        goChild(m, children[0]);
    } else {
        goPath(`${m.menu_path}`);
    }
};

onMounted(() => {
    isUser.value = userSession.isUserSession();
    userName.value = userSession.getUserInfo;
});
</script>

<style lang="scss" scoped>
@use '@@/__variables.scss' as *;

/* ──────────────────────────────────────────────
   Web 상단 내비게이션
   - 모바일(640px 미만)에서는 숨김
────────────────────────────────────────────── */
#comm-lnb-web {
    display: none;
    position: sticky;
    top: 0;
    z-index: 900;
    background: $yb-brown;
    border-bottom: 3px solid $yb-yellow;

    @include mobile {
        display: block;
    }
}

.lnb-web-inner {
    max-width: 1400px;
    margin: 0 auto;
    height: 46px;
    display: flex;
    align-items: center;
    padding: 0 20px;
    gap: 28px;
}

.lnb-brand {
    display: flex;
    align-items: center;
    gap: 8px;
    color: $yb-cream;
    font-weight: 800;
    font-size: 1rem;
    letter-spacing: .02em;
    white-space: nowrap;
    cursor: pointer;
    opacity: .95;

    .lnb-logo { width: 30px; height: 30px; flex-shrink: 0; }
    transition: opacity .15s;

    &:hover {
        opacity: 1;
    }
}

.lnb-menu {
    display: flex;
    align-items: center;
    height: 100%;
    list-style: none;
    margin: 0;
    padding: 0;
    flex: 1;
    gap: 4px;
}

.lnb-item {
    position: relative;
    height: 100%;
    display: flex;
    align-items: center;
    cursor: pointer;

    .lnb-item-label {
        display: flex;
        align-items: center;
        gap: 6px;
        height: 100%;
        padding: 0 14px;
        color: rgba($yb-cream, .78);
        font-size: 0.86rem;
        font-weight: 600;
        white-space: nowrap;
        border-bottom: 2px solid transparent;
        transition: color .15s, border-color .15s;
    }

    &:hover .lnb-item-label,
    &.active .lnb-item-label {
        color: $yb-cream;
        border-bottom-color: $yb-yellow;
    }

    .caret {
        width: 0;
        height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid currentColor;
        opacity: .8;
        transition: transform .15s ease;

        &.open {
            transform: rotate(180deg);
        }
    }
}

/* 드롭다운 */
.lnb-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    min-width: 180px;
    background: $dc-white;
    border: 1px solid $dc-gray-200;
    box-shadow: 0 10px 24px rgba(0, 0, 0, .12);
    list-style: none;
    margin: 0;
    padding: 0;
    z-index: 950;

    li {
        padding: 9px 12px;
        font-size: 0.82rem;
        font-weight: 500;
        color: $dc-gray-900;
        cursor: pointer;
        white-space: nowrap;
        transition: background .12s, color .12s;

        &:hover {
            background: $yb-cream;
        }

        &.active {
            background: $yb-yellow;
            color: $yb-ink;
            font-weight: 700;
        }
    }
}

.drop-enter-active,
.drop-leave-active {
    transition: opacity .12s ease, transform .12s ease;
}

.drop-enter-from,
.drop-leave-to {
    opacity: 0;
    transform: translateY(-4px);
}

.lnb-right {
    display: flex;
    align-items: center;
    white-space: nowrap;

    .lnb-user {
        color: rgba($dc-white, .78);
        font-size: 0.8rem;
        font-weight: 600;
    }
}

/* ──────────────────────────────────────────────
   Mobile 하단 탭 바
   - 데스크탑(640px 이상)에서는 숨김
────────────────────────────────────────────── */
#comm-lnb {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    /* index.html 이 viewport-fit=cover 라 웹뷰가 홈 인디케이터 아래까지 깔린다.
     * 인디케이터 높이를 더해 그리고, 그만큼을 padding-bottom 으로 비워
     * 아이콘/라벨은 항상 --lnb-height 안에 있게 한다(App.vue 의 --lnb-total 과 같은 출처). */
    height: var(--lnb-total);
    box-sizing: border-box;
    background-color: #FFF4C2;
    border-top: 1px solid #EAD9A6;
    padding: 6px 4px env(safe-area-inset-bottom, 0px);
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: minmax(0, 1fr);
    align-items: start;
    z-index: 1000;

    @include mobile {
        display: none;
    }

    .tab {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 3px;
        min-height: 48px;
        color: #6B5B4E;          // 비활성도 대비 4.5:1 이상 유지
        font-size: 11px;
        text-decoration: none;
        -webkit-tap-highlight-color: transparent;

        &.active {
            color: #5C3118;
            font-weight: 700;
        }
    }
}
</style>
