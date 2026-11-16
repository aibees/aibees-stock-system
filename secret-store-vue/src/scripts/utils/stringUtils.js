// 예전 createStatusKey/extractStatusKey(AES + SERVICE_KEY/ENCRYPT_KEY)는 쓰는 곳이 없어 지웠다.
// 그 키들이 화면 번들(JS)에 평문으로 실려 나가고 있었다 — 브라우저 코드에 비밀키를 두지 않는다.

export const isEmpty = (str) => {
    return str === undefined || str === null || str == '';
}
