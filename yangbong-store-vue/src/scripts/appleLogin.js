/**
 * Apple 로그인 — iOS 앱 전용(앱 안 네이티브 플러그인 ios/App/App/AppleSignInPlugin.swift, JS 이름 'AppleSignIn').
 *
 * 흐름: nonce 원문 생성 → 플러그인이 sha256(원문) 을 Apple 요청에 넣고 Apple 시트를 띄움
 *       → identityToken·authorizationCode 수신 → POST /api/oauth/apple (서버가 Apple 공개키로 검증).
 * 이름은 Apple 이 첫 로그인 때만 준다 → 함께 보낸다(서버는 표시용 이름에만 쓴다).
 * 계정 삭제 때는 같은 authorize 로 새 authorizationCode 를 받아 서버가 Apple 연결을 해지한다.
 */
import { Capacitor, registerPlugin } from '@capacitor/core';

const AppleSignIn = registerPlugin('AppleSignIn');

export const appleLoginAvailable = () => Capacitor.getPlatform() === 'ios';

const randomNonce = () =>
    Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('');

/**
 * Apple 시트를 띄워 인증한다.
 * @returns {Promise<null | {identityToken, authorizationCode, nonce, givenName, familyName, email}>}
 *          사용자가 취소하면 null. 그 밖의 실패는 throw.
 */
export async function authorizeApple() {
    const nonce = randomNonce();
    try {
        const res = await AppleSignIn.authorize({ nonce });
        return { ...res, nonce };
    } catch (e) {
        if (e?.code === 'CANCELED' || e?.message === 'canceled') return null;
        throw e;
    }
}
