/**
 * 광고 노출 판단/반응형 헬퍼.
 *
 * 노출 대상 = 광고가 켜져 있고(AD_ENABLED) 권한이 로드됐으며 AD_FREE 가 없는 사용자.
 * 비로그인(게스트)은 features 가 비어 있으므로 광고 대상이다.
 */
import { computed, ref, onMounted, onBeforeUnmount } from 'vue';
import { useRoute } from 'vue-router';
import { assUserSession } from './stores/user-stores.js';
import { AD_ENABLED } from './adConfig.js';
import { isAuthPath } from './authPaths.js';

export const useShowAds = () => {
    const store = assUserSession();
    const route = useRoute();
    return computed(() =>
        AD_ENABLED
        && store.access.loaded
        && !store.access.features.includes('AD_FREE')
        && !isAuthPath(route.path)   // 로그인·가입 화면에는 광고를 띄우지 않는다
    );
};

/** matchMedia 결과를 반응형 ref 로. */
export const useMediaQuery = (query) => {
    const matches = ref(false);
    let mq = null;
    const onChange = (e) => { matches.value = e.matches; };
    onMounted(() => {
        mq = window.matchMedia(query);
        matches.value = mq.matches;
        mq.addEventListener('change', onChange);
    });
    onBeforeUnmount(() => mq?.removeEventListener('change', onChange));
    return matches;
};
