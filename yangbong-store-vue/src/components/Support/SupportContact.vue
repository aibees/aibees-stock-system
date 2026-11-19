<template>
    <div id="support-contact">
        <BrandHeader title="문의하기" back="/menu" />
        <main class="sp">
            <section class="head">
                <img src="/img/emoji/honey.png" alt="" />
                <h1>궁금한 점을 알려주세요</h1>
                <p>메일로 문의해 주시면 확인 후 답변드릴게요.</p>
            </section>

            <section class="mail">
                <span class="label">문의 이메일</span>
                <b>{{ SUPPORT_EMAIL }}</b>
                <a class="cta" :href="mailto">메일 보내기</a>
                <button type="button" class="copy" @click="copy">{{ copied ? '복사했어요' : '이메일 주소 복사' }}</button>
            </section>

            <ul class="notes">
                <li>메일에는 앱 버전과 기기 종류가 자동으로 들어가요. 문제를 빠르게 확인하는 데 쓰여요.</li>
                <li>주민등록번호, 계좌 비밀번호 같은 정보는 보내지 마세요.</li>
                <li>종목 매수·매도에 대한 개별 상담은 해드리지 않아요.</li>
            </ul>

            <button type="button" class="faq-link" @click="router.push(FAQ_PATH)">자주 묻는 질문 먼저 보기 ›</button>
        </main>
    </div>
</template>

<script setup>
import { contactMailto, FAQ_PATH, SUPPORT_EMAIL } from '@scripts/support.js';

const router = useRouter();
const mailto = contactMailto();
const copied = ref(false);
const copy = async () => {
    try {
        await navigator.clipboard.writeText(SUPPORT_EMAIL);
        copied.value = true;
        setTimeout(() => { copied.value = false; }, 2000);
    } catch { /* 복사가 막힌 환경 — 주소가 화면에 보이므로 그대로 둔다 */ }
};
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#support-contact { min-height: 100vh; background: $card; color: $ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; }
button { border: 0; background: transparent; color: inherit; font: inherit; letter-spacing: inherit; cursor: pointer; }
.sp { max-width: 560px; margin: 0 auto; padding: 12px $pad-x 32px; box-sizing: border-box; }
.head { img { width: 44px; height: 44px; } h1 { margin: 12px 0 0; font-size: 23px; letter-spacing: -0.6px; } p { margin: 6px 0 0; font-size: 14.5px; color: $sub-ink; } }
.mail { margin-top: 22px; padding: 18px; border-radius: $radius; background: $honey-strip; display: flex; flex-direction: column;
    .label { font-size: 12.5px; color: $amber-700; font-weight: 700; }
    b { margin-top: 4px; font-size: 19px; color: $honey-ink; word-break: break-all; } }
.cta { margin-top: 16px; height: 52px; border-radius: $radius; background: #5A3C08; color: #fff; font-size: 16px; font-weight: 700; display: flex; align-items: center; justify-content: center; text-decoration: none; }
.copy { margin-top: 8px; height: 44px; border-radius: $radius; background: $card; color: $honey-ink; font-size: 14px; font-weight: 600; }
.notes { margin: 20px 0 0; padding: 0 0 0 18px; color: $sub-ink; font-size: 13.5px; line-height: 1.7; word-break: keep-all; }
.faq-link { margin-top: 20px; min-height: 44px; color: $sub; font-size: 14px; }
</style>
