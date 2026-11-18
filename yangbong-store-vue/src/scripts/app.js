import { createApp } from 'vue'
import App from '@/components/App.vue'
const app = createApp(App)

// ===== 레이어 팝업 드래그 디렉티브 =====
import draggable from './directives/draggable.js'
app.directive('draggable', draggable)
// =======================================

// ===== 차트 글꼴 =====
// Chart.js 는 캔버스에 직접 그려 CSS 글꼴을 따르지 않는다 → 기본 글꼴을 앱과 같은 Pretendard 로(2026-11-17 글꼴 통일).
import { Chart } from 'chart.js';
Chart.defaults.font.family = "'Pretendard', -apple-system, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif";
// =====================

// ===== global axios =====
import axios from 'axios';

const axiosInstance = axios.create({
    
})
app.provide('$axios', axiosInstance)
// ========================

// ===== pinia store Add =====
import { createPinia } from 'pinia';
import piniaPersist from 'pinia-plugin-persistedstate';
const pinia = createPinia();
pinia.use(piniaPersist)
app.use(pinia);
// ===========================

// ===== FontAwesomeIcon Add =====
import { library } from "@fortawesome/fontawesome-svg-core";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import { faMagnifyingGlass, faXmark, faMinus, faHome,
        faPlus, faDownload, faPen, faTrash, faComputer,
        faUpload, faBars, faSave, faCircleXmark, 
        faCaretLeft, faCaretRight, faBurger } from "@fortawesome/free-solid-svg-icons";

library.add(faMagnifyingGlass, faXmark, faMinus, faHome,
        faPlus, faDownload, faPen, faTrash, faUpload, 
        faBars, faSave, faCircleXmark, faCaretLeft, 
        faCaretRight, faBurger, faComputer);
app.component("font-awesome-icons", FontAwesomeIcon)
// ===============================

// ===== Event Bus =====
import mitt from 'mitt';
const emitter = new mitt();
app.provide('emitter', emitter);
// =====================

// ===== Router Resigrer =====
import { setRouterToApp } from './router'
setRouterToApp().then(router => {
    app.use(router);
    app.mount('#app');

    // ===== 푸시 알림(FCM) — 네이티브 앱에서만 동작 =====
    //   권한은 여기서 묻지 않는다. 관심 종목을 담고 '알림 받기'를 눌렀을 때 요청한다.
    //   광고 SDK(AdMob)와 iOS 추적(ATT) 팝업도 시작 때 띄우지 않고, 보상형 광고가 필요할 때 초기화한다(useAdMob.loadRewardedAd).
    import('./usePushNotifications').then(({ initPushNotifications }) => initPushNotifications());
    // ====================================================================
})
// ===========================

export default app
