// 사이트 전역 상수.
// 웹 버전은 닫는다 — 이 사이트의 버튼은 모두 '앱 설치하기'다(InstallButtons.vue).
// 스토어 주소는 출시 후 채운다. null 이면 '출시 준비 중'으로 보이고, 채우면 그 순간부터 설치 링크로 바뀐다.
export const CONTACT = 'chagoklabs@gmail.com';
// 운영사 차곡랩스 홈페이지(하단 'Chagok Labs가 만듭니다' 링크)
export const CHAGOK_URL = 'https://chagoklabs.com/';
export const APP_STORE_URL = null;   // 예: 'https://apps.apple.com/kr/app/id0000000000'
export const PLAY_STORE_URL = null;  // 예: 'https://play.google.com/store/apps/details?id=...'

export const STORES = [
  { key: 'ios', label: 'App Store', url: APP_STORE_URL },
  { key: 'android', label: 'Google Play', url: PLAY_STORE_URL },
].filter((s) => s.url);

// 접속한 기기에 맞는 스토어. 아이폰·아이패드 → App Store, 안드로이드 → Google Play, 그 외(PC) → null
export const detectPlatform = () => {
  const ua = navigator.userAgent || '';
  if (/android/i.test(ua)) return 'android';
  // iPadOS 13+ 는 맥으로 보이므로 터치 지원 여부로 구분
  if (/iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1)) return 'ios';
  return null;
};
