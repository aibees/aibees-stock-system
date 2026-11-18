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
                                {{ menuLabel(c) }}
                            </li>
                        </ul>
                    </transition>
                </li>
            </ul>
        </div>
    </nav>

    <!-- ── Mobile: 하단 탭 바 (홈 / 주식분석 / 트레이닝 / 메뉴) ──
         권한이 없는 탭은 그리지 않는다(access.paths — 서버가 내려준 접근 가능 경로). -->
    <nav id="comm-lnb" aria-label="주요 메뉴">
        <a v-for="t in visibleTabs" :key="t.key" class="tab" :class="{ active: isTabActive(t) }"
            :href="t.path" :aria-current="isTabActive(t) ? 'page' : undefined" @click.prevent="goPath(t.path)">
            <svg v-if="t.key === 'home'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"></path></svg>
            <!-- 트레이닝: 펼친 책 -->
            <svg v-else-if="t.key === 'training'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 6.5C10.3 5.3 7.9 4.7 4 4.7V18c3.9 0 6.3.6 8 1.8 1.7-1.2 4.1-1.8 8-1.8V4.7c-3.9 0-6.3.6-8 1.8z"></path><path d="M12 6.5v13.3"></path></svg>
            <!-- 분석: 돋보기 안에 작은 막대그래프(차트 탭의 꺾은선과 구분) -->
            <svg v-else-if="t.key === 'stocks'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="10.5" cy="10.5" r="7"></circle><path d="M21 21l-5.5-5.5"></path><path d="M7.5 13v-2M10.5 13V8M13.5 13v-3" stroke-width="1.8"></path></svg>
            <svg v-else-if="t.key === 'menu'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"></path></svg>
            <span class="tab-label">{{ t.label }}</span>
        </a>
    </nav>
</template>

<script setup>
import { menuLabel } from '@scripts/menuLabel.js';
import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { assUserSession } from "../../scripts/stores/user-stores";

const router = useRouter();
const route = useRoute();
const userSession = assUserSession();

/* ── 하단 탭바 ── */
const TABS = [
    { key: 'home',     label: '홈',       path: '/home',     match: ['/home'], always: true },
    // 트레이닝(차트·기업분석 보는 법): 정적 라우트라 권한과 무관하게 항상 보인다.
    { key: 'training', label: '트레이닝', path: '/training', match: ['/training'], always: true },
    // 주식분석: 누르면 매수추천이 열린다(/stock → 라우터 가드가 /stock/buy-target 으로, 2026-11-15 대시보드 대체).
    //   AI 분석·차트 확인 등 다른 하위 화면도 /stock 아래라 이 탭이 켜진다. 권한이 없으면 서버 경로에 없어 숨는다.
    { key: 'stocks',   label: '주식분석', path: '/stock',    match: ['/stock'] },
    // 전체 메뉴: 항상 맨 오른쪽에 둔다(권한과 무관 — 공개 메뉴라 비로그인도 열린다).
    { key: 'menu',     label: '메뉴',     path: '/menu',     match: ['/menu'], always: true },
];
// always 탭은 항상, 나머지는 서버가 이 사용자에게 허용한 경로(access.paths)에 있을 때만 보인다.
// 양봉상회에는 매매(트레이드·자동매매) 탭이 없다(2026-11-15 분리).
const visibleTabs = computed(() =>
    TABS.filter(t => t.always || userSession.access.paths.includes(t.path)));
// 더 구체적인 경로의 탭이 있으면 그쪽이 활성이 되도록(접두사가 겹치는 탭이 같이 켜지지 않게) 한다.
const isTabActive = (t) => {
    const hit = (tab) => tab.match.some(p => route.path === p || route.path.startsWith(p + '/'));
    if (!hit(t)) return false;
    return !TABS.some(o => o !== t && o.path.startsWith(t.path + '/') && hit(o));
};

const isUser = ref(false);
const userName = ref('');
// 권한 반영본 메뉴(스토어). 로그인/로그아웃으로 바뀌면 자동 반영되도록 computed 로 읽는다.
const allMenu = computed(() => userSession.user.menuList ?? []);
const openCode = ref('');

// 메뉴 권한은 서버(/master/menus/my → role_menu)가 걸러서 내려준 menuList 를 그대로 쓴다.

/* ── 노출 가능한 최상위 메뉴 (표시/사용/권한 필터 + 정렬) ── */
const TRAINING_MENU = { menu_code: 'Training', menu_path: 'training', menu_name: '트레이닝', menu_title: '트레이닝', sort: -1, children: [] };
const topMenus = computed(() => {
    return [TRAINING_MENU, ...(allMenu.value ?? [])]
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
        goPath(`/${String(m.menu_path).replace(/^\/+/, '')}`);
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
    background: $dc-white;
    border-bottom: 1px solid #E5E8EB;
    font-family: 'Pretendard', -apple-system, 'Apple SD Gothic Neo', sans-serif;

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
    color: #191F28;
    font-weight: 700;
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
        color: #8B95A1;
        font-size: 0.86rem;
        font-weight: 600;
        white-space: nowrap;
        border-bottom: 2px solid transparent;
        transition: color .15s, border-color .15s;
    }

    &:hover .lnb-item-label,
    &.active .lnb-item-label {
        color: #191F28;
        border-bottom-color: #191F28;
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
            background: #F2F4F6;
        }

        &.active {
            background: #F2F4F6;
            color: #191F28;
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
    background-color: #FFFFFF;
    border-top: 1px solid #ECEBE6;
    padding: 6px 4px env(safe-area-inset-bottom, 0px);
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: minmax(0, 1fr);
    align-items: start;
    z-index: 1000;
    font-family: 'Pretendard', -apple-system, 'Apple SD Gothic Neo', sans-serif;

    @include mobile {
        display: none;
    }

    .tab {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 4px;
        min-height: 48px;
        color: #8B95A1;          // 비활성: 회색(흰 바탕 대비 3:1 이상, 아이콘+라벨 함께)
        font-size: 11px;
        text-decoration: none;
        -webkit-tap-highlight-color: transparent;

        svg { width: 22px; height: 22px; }

        &.active {
            color: #191F28;
            font-weight: 600;
            svg { fill: #F8C844; }   // 꿀빛 포인트: 지금 탭 아이콘만 꿀색으로 채운다(선은 진한 글자색)
        }
    }
}
</style>
