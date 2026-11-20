<template>
  <main class="doc wrap">
  <h1>개인정보 처리방침</h1>
  <p class="meta">시행일: 2026년 11월 19일</p>

  <p>차곡랩스(chagoklabs)는 양봉상회(이하 “서비스”)를 운영하며, 「개인정보 보호법」 등 관련 법령을 지킵니다. 이 방침은 서비스가 어떤 개인정보를 왜 수집하고, 어떻게 이용·보관·파기하는지 안내합니다.</p>

  <h2>1. 개인정보의 처리 목적</h2>
  <ul>
    <li><strong>회원 관리</strong> — 소셜 로그인을 통한 회원 식별, 로그인 유지, 부정 이용 방지</li>
    <li><strong>서비스 제공</strong> — 주식 정보·종목 추천·분석 제공, 관심 종목 관리</li>
    <li><strong>알림 발송</strong> — 앱 푸시 알림</li>
    <li><strong>공지·문의 응대</strong> — 공지사항 전달, 문의 접수와 답변</li>
    <li><strong>광고 게재</strong> — 앱 내 광고 표시(무료 서비스 운영)</li>
  </ul>

  <h2>2. 처리하는 개인정보 항목</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>구분</th><th>항목</th><th>수집 방법</th></tr></thead>
      <tbody>
        <tr><td>소셜 로그인 (필수)</td><td>회원 식별값, 이름(또는 별명), 이메일 주소</td><td>네이버·구글 계정으로 가입·로그인할 때 해당 서비스로부터 제공</td></tr>
        <tr><td>이용자 입력 (선택)</td><td>관심 종목</td><td>이용자가 직접 입력</td></tr>
        <tr><td>자동 생성</td><td>앱 푸시 알림용 기기 토큰</td><td>앱에서 알림을 허용할 때 생성</td></tr>
        <tr><td>자동 수집</td><td>접속 IP 주소, 접속 일시, 기기·앱 정보(User-Agent), 서비스 이용 기록</td><td>서비스 이용 과정에서 자동 수집</td></tr>
        <tr><td>광고 (앱)</td><td>광고 식별자(Android 광고 ID, iOS IDFA), 기기 정보</td><td>앱에서 광고를 표시할 때 광고 SDK가 수집</td></tr>
      </tbody>
    </table>
  </div>
  <p class="note">선택 항목은 해당 기능을 쓰지 않으면 수집하지 않습니다. 선택 항목 입력을 거부해도 그 기능 외의 서비스는 이용할 수 있습니다.</p>

  <h2>3. 개인정보의 처리 및 보유 기간</h2>
  <dl>
    <div><dt>회원 정보 및 이용자 입력 정보</dt><dd>회원 탈퇴 시까지 보관하며, 탈퇴하면 지체 없이 파기합니다.</dd></div>
    <div><dt>앱 푸시 기기 토큰</dt><dd>로그아웃·앱 삭제로 토큰이 무효가 되거나 탈퇴하면 삭제합니다.</dd></div>
    <div><dt>접속 기록</dt><dd>「통신비밀보호법」에 따라 3개월간 보관한 뒤 파기합니다.</dd></div>
  </dl>
  <p class="note">관계 법령에서 보존을 요구하는 정보는 해당 법령이 정한 기간 동안 보관합니다.</p>

  <h2>4. 개인정보의 제3자 제공</h2>
  <p>차곡랩스는 이용자의 개인정보를 제3자에게 제공하지 않습니다.</p>

  <h2>5. 개인정보 처리 위탁</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>수탁자</th><th>위탁 업무</th><th>처리 항목</th></tr></thead>
      <tbody>
        <tr><td>네이버 주식회사</td><td>소셜 로그인 인증</td><td>네이버 계정 식별 정보</td></tr>
        <tr><td>Google LLC</td><td>소셜 로그인 인증</td><td>구글 계정 식별 정보</td></tr>
        <tr><td>Google LLC (Firebase)</td><td>앱 푸시 알림 발송</td><td>푸시 기기 토큰, 알림 내용</td></tr>
        <tr><td>Google LLC (AdMob)</td><td>앱 내 광고 게재</td><td>광고 식별자, 기기 정보</td></tr>
        <tr><td>Cloudflare, Inc.</td><td>서비스 트래픽 전달 및 보안</td><td>접속 IP 주소, 접속 기록</td></tr>
      </tbody>
    </table>
  </div>
  <p class="note">서비스의 AI 분석 기능은 종목·시세 데이터만 외부 AI 서비스(Anthropic)로 보내며, 이용자의 개인정보는 보내지 않습니다.</p>

  <h2>6. 개인정보의 국외 이전</h2>
  <p>위 수탁자 중 Google LLC와 Cloudflare, Inc.는 국외에 서버를 두고 있어, 서비스 이용 과정에서 해당 항목이 네트워크를 통해 국외로 전송됩니다.</p>
  <ul>
    <li><strong>이전받는 자</strong>: Google LLC(미국), Cloudflare, Inc.(미국)</li>
    <li><strong>이전 항목·목적</strong>: 5항의 위탁 업무와 처리 항목과 같습니다.</li>
    <li><strong>이전 시기·방법</strong>: 서비스 이용 시점에 암호화된 네트워크로 전송</li>
    <li><strong>보유 기간</strong>: 위탁 목적 달성 시 또는 위탁 계약 종료 시까지</li>
  </ul>
  <p class="note">국외 이전을 원하지 않으면 해당 기능(구글 로그인, 앱 푸시 알림)을 쓰지 않거나 회원 탈퇴를 요청할 수 있습니다. 이 경우 일부 기능을 이용할 수 없습니다.</p>

  <h2>7. 이용자의 권리와 행사 방법</h2>
  <p>이용자는 언제든지 다음 권리를 행사할 수 있습니다.</p>
  <ul>
    <li>자신의 개인정보 열람·정정·삭제·처리정지 요청</li>
    <li>개인정보 수집·이용 동의 철회 및 회원 탈퇴</li>
    <li>앱 푸시 알림 수신 거부(기기 설정 또는 앱 설정)</li>
  </ul>
  <p>권리 행사는 아래 13항의 문의처로 요청할 수 있으며, 차곡랩스는 지체 없이 조치합니다.</p>

  <h2>8. 개인정보의 파기</h2>
  <p>보유 기간이 끝나거나 처리 목적이 달성된 개인정보는 지체 없이 파기합니다. 전자 파일 형태의 정보는 복구할 수 없는 방법으로 영구 삭제합니다.</p>

  <h2>9. 개인정보의 안전성 확보 조치</h2>
  <ul>
    <li>개인정보 처리 시스템 접근 권한을 운영자로 제한</li>
    <li>모든 통신 구간에 HTTPS(TLS) 암호화 적용</li>
    <li>데이터베이스를 외부 네트워크에서 직접 접근할 수 없는 곳에 두고 접근 기록 관리</li>
  </ul>

  <h2>10. 자동 수집 장치와 광고 식별자</h2>
  <p>앱은 로그인 상태 유지를 위해 기기 안 저장소에 로그인 정보와 자동 로그인 설정을 저장합니다. 로그아웃하거나 앱을 삭제하면 지워집니다. 광고나 제3자 추적 목적의 쿠키는 쓰지 않습니다.</p>
  <p>앱은 광고 게재를 위해 광고 식별자를 사용합니다. 다음 방법으로 맞춤형 광고를 거부할 수 있습니다.</p>
  <ul>
    <li><strong>Android</strong>: 설정 → Google → 광고 → 광고 ID 삭제</li>
    <li><strong>iOS</strong>: 설정 → 개인정보 보호 및 보안 → 추적 → 앱의 추적 요청 허용 끄기</li>
  </ul>

  <h2>11. 아동의 개인정보 보호</h2>
  <p>서비스는 만 14세 이상만 가입할 수 있으며, 만 14세 미만 아동의 개인정보를 수집하지 않습니다. 만 14세 미만 아동의 정보가 수집된 사실을 알게 되면 즉시 파기합니다.</p>

  <h2>12. 개인정보 처리방침의 변경</h2>
  <p>이 방침이 바뀌면 시행일 최소 7일 전에 이 페이지와 서비스 공지사항으로 알립니다. 수집 항목이 늘어나는 등 이용자 권리에 중요한 변경이 있으면 30일 전에 알리고 필요한 경우 다시 동의를 받습니다.</p>

  <h2>13. 개인정보 보호책임자 및 문의</h2>
  <dl>
    <div><dt>개인정보 보호책임자</dt><dd>(성명)</dd></div>
    <div><dt>이메일</dt><dd><a :href="`mailto:${CONTACT}`">{{ CONTACT }}</a></dd></div>
  </dl>
  <p style="margin-top:12px">개인정보 침해에 대한 신고나 상담이 필요하면 아래 기관에 문의할 수 있습니다.</p>
  <ul>
    <li>개인정보침해신고센터 (국번 없이 118, <a href="https://privacy.kisa.or.kr" rel="noopener">privacy.kisa.or.kr</a>)</li>
    <li>개인정보분쟁조정위원회 (1833-6972, <a href="https://www.kopico.go.kr" rel="noopener">www.kopico.go.kr</a>)</li>
    <li>대검찰청 사이버수사과 (국번 없이 1301, <a href="https://www.spo.go.kr" rel="noopener">www.spo.go.kr</a>)</li>
    <li>경찰청 사이버수사국 (국번 없이 182, <a href="https://ecrm.police.go.kr" rel="noopener">ecrm.police.go.kr</a>)</li>
  </ul>
  </main>
</template>

<script setup>
// 앱(App Store·Play) 심사와 가입 화면이 이 주소(/privacy)를 가리킨다.
// 내용을 바꾸면 시행일을 올리고, yangbong-store-vue/src/scripts/privacyPolicy.js 와 어긋나지 않는지 확인한다.
import { CONTACT } from '@/site.js';
</script>
