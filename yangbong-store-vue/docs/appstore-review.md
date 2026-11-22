# 양봉상회 앱스토어 심사 준비

기준일: 2026-11-22. 앱 코드(`yangbong-store-vue`)와 iOS 설정(`ios/App`)을 보고 정리했다. 제출 화면(App Store Connect)에 그대로 옮겨 쓴다.

## 1. 현재 상태 점검

| 항목 | 상태 | 근거 / 할 일 |
|---|---|---|
| Apple 로그인 (가이드라인 4.8) | 완료 | iOS 앱에 `Apple로 계속하기`, 서버 `POST /api/oauth/apple`, entitlement `com.apple.developer.applesignin` |
| 앱 안 계정 삭제 (5.1.1(v)) | 완료 | `메뉴 > 계정 설정 > 계정 삭제`. Apple 연결 계정은 재인증 후 Apple 토큰 해지 |
| 추적 권한(ATT) 문구 | 완료 | `NSUserTrackingUsageDescription` 있음. 광고를 처음 볼 때 요청 |
| 푸시 권한 | 완료 | 앱 시작 때 묻지 않고, 관심 종목을 담은 뒤 `알림 받기`에서 요청 |
| 개인정보 처리방침·이용약관 URL | 배포 필요 | `https://yangbong-store.chagoklabs.com/privacy`, `/terms` — 개정본이 main 에 있고 서버 배포 전 |
| 결제(인앱 구독) | 출시 범위 밖 | 결제 코드·구매 버튼 없음. 프리미엄 탭은 `프리미엄은 준비 중이에요` 안내만. 유사투자자문업 신고 후 추가 |
| 아이패드 지원 | **결정 필요** | `TARGETED_DEVICE_FAMILY = "1,2"` → 아이패드 스크린샷(13인치 2064×2752) 필수 |
| 아이폰 가로 화면 | **결정 필요** | 아이폰도 가로 회전 허용 상태. 화면이 세로 기준이라 세로 고정 권장 |
| 광고 게이트 | 확인 | 주목 종목·종목 상세·차트에 N번 들어갈 때마다 보상형 광고. 심사 메모에 설명 |

## 2. 심사팀 메모 (App Review Information > Notes, 영어)

```
Yangbong (양봉상회) is an educational stock-information app for beginner investors in Korea.

What the app does
- Shows end-of-day market summaries and stocks that match technical-indicator conditions the user selects
  (volume, moving averages, Bollinger Bands, MACD), with plain-language reasons.
- Provides free lessons, quizzes and a glossary about reading charts and managing risk.

What the app does NOT do
- It does not execute trades, connect to brokerage accounts, hold user funds, or provide one-to-one
  investment advice. All users see the same information; nothing is personalized advice.
- Every analysis screen shows that the information is for reference only and investment decisions are
  the user's own responsibility.

Accounts
- Most features (home, stock lists, training) work without an account.
- Sign in with Apple, Naver, Google or email is available. Account deletion: Menu > 계정 설정 > 계정 삭제.
- Demo account for review: ID ________ / Password ________

Ads
- The app shows rewarded ads (Google AdMob) before some analysis screens. Tracking permission (ATT) is
  requested only when an ad is first shown. Declining tracking does not limit any feature.

Premium
- A premium tab is visible but disabled ("coming soon"). There are no in-app purchases in this version.
```

> 데모 계정은 심사 전에 실서버에 만들어 채운다. 실제 비밀번호를 이 파일에 적지 않는다.

## 3. 앱 개인정보 라벨 (App Privacy)

개인정보 처리방침(2026-12-01 시행)과 같은 내용으로 답한다.

| 데이터 유형 | 수집 | 사용자와 연결 | 추적에 사용 | 목적 |
|---|---|---|---|---|
| 연락처 정보 > 이메일 주소 | 예 | 예 | 아니요 | 앱 기능(로그인), 고객 지원 |
| 연락처 정보 > 이름 | 예 | 예 | 아니요 | 앱 기능 |
| 식별자 > 사용자 ID | 예 | 예 | 아니요 | 앱 기능 |
| 식별자 > 기기 ID (IDFA) | 예 | 예 | **예** (ATT 허용 시) | 타사 광고 |
| 사용 데이터 > 제품 상호작용 | 예 | 예 | 아니요 | 분석, 앱 기능 |
| 사용 데이터 > 광고 데이터 | 예 | 아니요 | 예 (ATT 허용 시) | 타사 광고 |
| 기타 > 푸시 기기 토큰 | 예 | 예 | 아니요 | 앱 기능(알림) |
| 구매 항목 | 아니요 | — | — | 구독을 추가하는 버전에서 다시 답한다 |

> AdMob 이 실제로 무엇을 수집하는지는 Google 의 앱 개인정보 라벨 안내와 다시 맞춰 본다.

## 4. 스토어 정보

| 항목 | 값 |
|---|---|
| 카테고리 | 금융(주) · 교육(부) |
| 지원 URL | `https://yangbong-store.chagoklabs.com/` (고객지원 메일 chagoklabs@gmail.com) |
| 개인정보 처리방침 URL | `https://yangbong-store.chagoklabs.com/privacy` |
| 스크린샷 | 아이폰 6.9인치 6장 완료(`store-assets/ios-6.9`). 아이패드 지원 시 13인치 추가 |
| 연령 등급 | 도박·성인·폭력 없음. 질문지 답변 후 결과 확인 |

## 5. 실기기 점검표 (TestFlight)

- [ ] 처음 설치 → 소개 → 질문 3개 → 맞는 종목 3개 → 관심 종목 담기 → `알림 받기` 권한 창
- [ ] 앱 시작 때 권한 창이 뜨지 않는다(알림·추적 모두)
- [ ] 주목 종목에 들어갈 때 광고 → 추적 권한 창이 그때 한 번 뜬다
- [ ] Apple 로그인으로 새 가입 → 약관 동의 → 홈
- [ ] 기존 회원 로그인 → 새 약관(2026-12-01) 재동의 화면
- [ ] 계정 삭제(이메일 계정, Apple 계정 각각) → 다시 로그인 안 됨
- [ ] 고객지원: 자주 묻는 질문, 문의하기(메일 앱 열림), 이용약관, 개인정보 처리방침, 오픈소스 라이선스
- [ ] 아이폰 가로 회전(세로 고정 여부 결정 후)
- [ ] 아이패드(지원 결정 시): 홈·주목 종목·트레이닝 화면 배치

## 6. 반려되기 쉬운 지점

- **3.2.1(viii) 금융 서비스 앱:** 매매·투자 서비스 앱은 금융기관만 제출할 수 있다. 양봉상회는 매매·계좌 연동이 없는 정보·교육 앱이라는 점을 심사 메모 첫 줄에 적었다. 문의가 오면 같은 내용으로 답한다.
- **2.1 앱 완성도:** 프리미엄 탭이 비어 보이지 않게 `준비 중` 안내가 있는지, 데모 계정이 실제로 로그인되는지 제출 전에 확인한다.
- **5.1.1 개인정보:** 처리방침 URL 이 실제로 열려야 한다(배포 전이면 반려).
