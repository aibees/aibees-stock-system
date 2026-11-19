<template>
    <div id="support-doc">
        <BrandHeader :title="doc.title" back="/menu" />
        <main class="sp">
            <p v-if="doc.version" class="ver">시행일 {{ doc.version }}</p>
            <section v-for="sec in doc.sections" :key="sec.title" class="sec">
                <h2>{{ sec.title }}</h2>
                <p v-for="(p, i) in sec.body" :key="i">{{ p }}</p>
            </section>
        </main>
    </div>
</template>

<script setup>
/** 이용약관 · 개인정보 처리방침 보기(가입 동의 화면과 같은 원문). */
import { TERMS_SECTIONS, TERMS_VERSION } from '@scripts/termsOfService.js';
import * as privacy from '@scripts/privacyPolicy.js';
import { PRIVACY_PATH } from '@scripts/support.js';

const route = useRoute();
const doc = computed(() => (route.path === PRIVACY_PATH
    ? { title: '개인정보 처리방침', sections: privacy.PRIVACY_POLICY_SECTIONS, version: privacy.PRIVACY_POLICY_VERSION }
    : { title: '이용약관', sections: TERMS_SECTIONS, version: TERMS_VERSION }));
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#support-doc { min-height: 100vh; background: $card; color: $ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; }
.sp { max-width: 720px; margin: 0 auto; padding: 8px $pad-x 40px; box-sizing: border-box; }
.ver { margin: 0 0 4px; font-size: 13px; color: $sub; }
.sec { padding: 16px 0; border-bottom: 1px solid $line;
    h2 { margin: 0 0 8px; font-size: 16px; }
    p { margin: 0 0 6px; font-size: 14.5px; line-height: 1.65; color: $sub-ink; word-break: keep-all; } }
</style>
