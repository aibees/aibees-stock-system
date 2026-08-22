/**
 * FCM 푸시 알림 등록/수신 처리.
 *
 * - 웹(브라우저)에서는 아무 것도 하지 않는다 — Capacitor.isNativePlatform() 로 분기.
 *   (@capacitor/push-notifications 는 네이티브 전용 — 웹에서 register() 호출 시 에러남)
 * - 흐름: 권한 요청 → register() → 'registration' 이벤트로 토큰 수신 →
 *   백엔드(app/api/v1/notify/register, py-stock-batch)에 업로드.
 * - "앱이 꺼져있어도 알림이 가야 한다"는 FCM 의 기본 동작(OS 시스템 알림)으로
 *   충족된다 — 이 파일이 직접 처리하는 건 "앱이 켜져있을 때(포그라운드) 뜨는
 *   toast" 뿐이다. 포그라운드에서는 OS 배너가 기본적으로 안 뜨기 때문에
 *   mariaToast 로 대신 보여준다.
 */
import { Capacitor } from '@capacitor/core';
import { PushNotifications } from '@capacitor/push-notifications';
import { batchApi } from './aibeesApi';
import mariaToast from './mariaToast';
import { assUserSession } from './stores/user-stores';

let initialized = false;

export async function initPushNotifications() {
    if (initialized) return;
    if (!Capacitor.isNativePlatform()) return; // 웹 배포는 skip
    initialized = true;

    try {
        let perm = await PushNotifications.checkPermissions();
        if (perm.receive === 'prompt') {
            perm = await PushNotifications.requestPermissions();
        }
        if (perm.receive !== 'granted') {
            console.warn('[push] 알림 권한이 거부되었습니다.');
            return;
        }

        await PushNotifications.register();

        PushNotifications.addListener('registration', (token) => {
            registerTokenToServer(token.value);
        });

        PushNotifications.addListener('registrationError', (err) => {
            console.error('[push] 토큰 등록 실패', err);
        });

        // 포그라운드 수신 → toast. (백그라운드/종료 상태 수신은 OS 가 시스템
        // 알림으로 대신 띄운다 — 여기서 처리할 필요 없음)
        PushNotifications.addListener('pushNotificationReceived', (noti) => {
            const title = noti.title || noti.data?.title || '알림';
            const body = noti.body || noti.data?.body || '';
            mariaToast.info(body ? `${title} - ${body}` : title);
        });

        // 알림을 탭해서 앱을 열었을 때. 지금은 별도 화면 이동 없이 로그만 —
        // 필요해지면 noti.notification.data.batch_code 등으로 라우팅 추가.
        PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
            console.log('[push] 알림 탭:', action.notification);
        });
    } catch (e) {
        console.error('[push] 초기화 실패', e);
    }
}

async function registerTokenToServer(deviceToken) {
    try {
        const userSession = assUserSession();
        const platform = Capacitor.getPlatform(); // 'ios' | 'android'
        const userId = userSession.isUserSession()
            ? (userSession.user.loginInfo.user_id || null)
            : null;
        const roles = userSession.getRole ?? [];

        await batchApi.post('/api/v1/notify/register', {
            device_token: deviceToken,
            platform,
            user_id: userId,
            roles,
        });
    } catch (e) {
        console.error('[push] 서버 등록 실패', e);
    }
}
