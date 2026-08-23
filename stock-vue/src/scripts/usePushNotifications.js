/**
 * FCM 푸시 알림 등록/수신 처리.
 *
 * @capacitor-firebase/messaging 사용 (기존 @capacitor/push-notifications 에서 교체).
 * 교체 이유: @capacitor/push-notifications 는 iOS에서 Firebase SDK를 거치지 않고
 * APNs raw device token(hex 문자열)을 그대로 'registration' 이벤트로 넘겨준다.
 * 서버(firebase-admin)는 FCM 등록 토큰을 기대하는데 raw APNs token을 그대로 보내면
 * "The registration token is not a valid FCM registration token" (INVALID_ARGUMENT)
 * 로 거부된다. @capacitor-firebase/messaging 은 네이티브 FirebaseMessaging SDK를 통해
 * APNs token → FCM token 교환을 내부적으로 처리해서 진짜 FCM 토큰을 돌려준다.
 * (Android는 원래부터 FCM SDK를 직접 쓰므로 이 문제가 없었다.)
 *
 * - 웹(브라우저)에서는 아무 것도 하지 않는다 — Capacitor.isNativePlatform() 로 분기.
 * - 흐름: 권한 요청 → (플러그인이 내부적으로 APNs 등록 + FCM 토큰 교환) →
 *   'tokenReceived' 이벤트로 FCM 토큰 수신 → 백엔드(app/api/v1/notify/register,
 *   py-stock-batch)에 업로드. 이벤트가 늦게 올 경우를 대비해 getToken() 도 한 번
 *   직접 호출해서 즉시 시도해본다(실패해도 무시 — 이벤트로 나중에 들어옴).
 * - "앱이 꺼져있어도 알림이 가야 한다"는 FCM 의 기본 동작(OS 시스템 알림)으로
 *   충족된다 — 이 파일이 직접 처리하는 건 "앱이 켜져있을 때(포그라운드) 뜨는
 *   toast" 뿐이다. 포그라운드에서는 OS 배너가 기본적으로 안 뜨기 때문에
 *   mariaToast 로 대신 보여준다.
 */
import { Capacitor } from '@capacitor/core';
import { FirebaseMessaging } from '@capacitor-firebase/messaging';
import { batchApi } from './aibeesApi';
import mariaToast from './mariaToast';
import { assUserSession } from './stores/user-stores';

let initialized = false;
let lastSentToken = null;

export async function initPushNotifications() {
    console.log("[initPushNotifications] INIT : " + initialized);
    if (initialized) {
        return;
    }
    console.log("[initPushNotifications] isNativePlatform" + Capacitor.isNativePlatform())
    if (!Capacitor.isNativePlatform()) {
        return;
    } // 웹 배포는 skip

    initialized = true;

    try {
        let perm = await FirebaseMessaging.checkPermissions();
        console.log("[initPushNotifications] PERM : ");
        console.log(perm);
        if (perm.receive === 'prompt') {
            perm = await FirebaseMessaging.requestPermissions();
        }
        if (perm.receive !== 'granted') {
            console.warn('[push] 알림 권한이 거부되었습니다.');
            return;
        }

        // FCM 토큰이 (재)생성될 때마다 호출됨 — 최초 발급뿐 아니라 토큰 갱신 시에도 온다.
        FirebaseMessaging.addListener('tokenReceived', (event) => {
            console.log('[push] tokenReceived 이벤트 수신, token 길이=' + (event?.token?.length ?? 0)
                + ', token 앞 12자=' + (event?.token?.slice(0, 12) ?? ''));
            registerTokenToServer(event.token);
        });

        // APNs raw token 수신 로그(디버깅용) — 이게 뜨는데 tokenReceived 가 안 뜨면
        // Firebase 프로젝트에 APNs 인증키(Firebase Console > Cloud Messaging)가
        // 등록 안 되어 있을 가능성이 큼.
        FirebaseMessaging.addListener('apnsTokenReceived', (event) => {
            console.log('[push] apnsTokenReceived(raw APNs token) 앞 12자=' + (event?.token?.slice(0, 12) ?? ''));
        });

        console.log('[push] getToken() 직접 호출 시도');
        try {
            const { token } = await FirebaseMessaging.getToken();
            console.log('[push] getToken() 성공, token 앞 12자=' + (token?.slice(0, 12) ?? ''));
            registerTokenToServer(token);
        } catch (e) {
            // 아직 APNs 등록이 안 끝난 시점일 수 있음 — tokenReceived 이벤트로 나중에 들어옴.
            console.warn('[push] getToken() 즉시 호출 실패(무시, tokenReceived 대기):', e?.message);
        }

        // 포그라운드 수신 → toast. (백그라운드/종료 상태 수신은 OS 가 시스템
        // 알림으로 대신 띄운다 — 여기서 처리할 필요 없음)
        FirebaseMessaging.addListener('notificationReceived', (event) => {
            const noti = event.notification || {};
            const title = noti.title || noti.data?.title || '알림';
            const body = noti.body || noti.data?.body || '';
            mariaToast.info(body ? `${title} - ${body}` : title);
        });

        // 알림을 탭해서 앱을 열었을 때. 지금은 별도 화면 이동 없이 로그만 —
        // 필요해지면 event.notification.data.batch_code 등으로 라우팅 추가.
        FirebaseMessaging.addListener('notificationActionPerformed', (event) => {
            console.log('[push] 알림 탭:', event.notification);
        });
    } catch (e) {
        console.error('[push] 초기화 실패', e);
    }
}

async function registerTokenToServer(deviceToken) {
    if (!deviceToken || deviceToken === lastSentToken) {
        return; // 같은 토큰 중복 전송 방지(tokenReceived + getToken() 둘 다 올 수 있음)
    }
    lastSentToken = deviceToken;

    try {
        const userSession = assUserSession();
        const platform = Capacitor.getPlatform(); // 'ios' | 'android'
        const userId = userSession.isUserSession()
            ? (userSession.user.loginInfo.user_id || null)
            : null;
        const roles = userSession.getRole ?? [];

        console.log('[push] 서버 등록 요청 → /api/v1/notify/register platform=' + platform
            + ' user_id=' + userId + ' baseURL=' + (batchApi.defaults?.baseURL ?? '(none)'));

        const resp = await batchApi.post('/api/v1/notify/register', {
            device_token: deviceToken,
            platform,
            user_id: userId,
            roles,
        });

        console.log('[push] 서버 등록 성공', JSON.stringify(resp.data));
    } catch (e) {
        // [디버깅] 여기 안 뜨고 tokenReceived 로그만 있으면 → nginx 라우팅/CORS/네트워크 문제.
        console.error('[push] 서버 등록 실패', e?.response?.status, e?.message, JSON.stringify(e?.response?.data ?? ''));
    }
}
