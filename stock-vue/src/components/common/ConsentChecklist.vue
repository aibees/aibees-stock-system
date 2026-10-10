<template>
    <section class="consent">
        <label class="cc-row cc-all">
            <input type="checkbox" :checked="allChecked" @change="setAll($event.target.checked)" />
            <span>전체 동의</span>
        </label>

        <ul class="cc-list">
            <li>
                <label class="cc-row">
                    <input type="checkbox" :checked="modelValue.age14" @change="set('age14', $event.target.checked)" />
                    <span><b>[필수]</b> 만 14세 이상입니다</span>
                </label>
            </li>

            <li>
                <div class="cc-line">
                    <label class="cc-row">
                        <input type="checkbox" :checked="modelValue.terms" @change="set('terms', $event.target.checked)" />
                        <span><b>[필수]</b> 이용약관 동의</span>
                    </label>
                    <button type="button" class="cc-view" :aria-expanded="open === 'terms' ? 'true' : 'false'"
                        @click="toggle('terms')">{{ open === 'terms' ? '접기' : '보기' }}</button>
                </div>
                <div v-if="open === 'terms'" class="cc-doc" tabindex="0">
                    <div v-for="sec in TERMS_SECTIONS" :key="sec.title" class="cc-doc-sec">
                        <h4>{{ sec.title }}</h4>
                        <p v-for="(p, i) in sec.body" :key="i">{{ p }}</p>
                    </div>
                </div>
            </li>

            <li>
                <div class="cc-line">
                    <label class="cc-row">
                        <input type="checkbox" :checked="modelValue.privacy" @change="set('privacy', $event.target.checked)" />
                        <span><b>[필수]</b> 개인정보 수집·이용 동의</span>
                    </label>
                    <button type="button" class="cc-view" :aria-expanded="open === 'privacy' ? 'true' : 'false'"
                        @click="toggle('privacy')">{{ open === 'privacy' ? '접기' : '보기' }}</button>
                </div>
                <div v-if="open === 'privacy'" class="cc-doc" tabindex="0">
                    <dl class="cc-summary">
                        <div v-for="row in CONSENT_SUMMARY" :key="row.label">
                            <dt>{{ row.label }}</dt>
                            <dd>{{ row.value }}</dd>
                        </div>
                    </dl>
                    <div v-for="sec in PRIVACY_POLICY_SECTIONS" :key="sec.title" class="cc-doc-sec">
                        <h4>{{ sec.title }}</h4>
                        <p v-for="(p, i) in sec.body" :key="i">{{ p }}</p>
                    </div>
                </div>
            </li>
        </ul>
    </section>
</template>

<script setup>
/**
 * 가입 동의 체크리스트 — 만 14세 / 이용약관 / 개인정보 수집·이용을 항목별로 따로 받는다.
 * v-model: { age14, terms, privacy } (모두 boolean). 서버에는 항목별 동의와 문구 버전을 함께 보낸다
 * (TERMS_VERSION / PRIVACY_POLICY_VERSION). 네이버 가입(SignupConsent)과 이메일 가입(Signup)이 같이 쓴다.
 */
import { TERMS_SECTIONS } from '@scripts/termsOfService.js';
import { CONSENT_SUMMARY, PRIVACY_POLICY_SECTIONS } from '@scripts/privacyPolicy.js';

const props = defineProps({
    modelValue: { type: Object, required: true },
});
const emit = defineEmits(['update:modelValue']);

const KEYS = ['age14', 'terms', 'privacy'];
const allChecked = computed(() => KEYS.every(k => props.modelValue[k]));
const set = (key, val) => emit('update:modelValue', { ...props.modelValue, [key]: val });
const setAll = (val) => emit('update:modelValue', Object.fromEntries(KEYS.map(k => [k, val])));

const open = ref(null);
const toggle = (key) => { open.value = open.value === key ? null : key; };
</script>

<style scoped lang="scss">
$hero:  #74462A;
$brown: #7A4423;
$ink:   #2B1D14;
$sub:   #6B5B4E;
$line:  #EFE2BC;

.consent { display: flex; flex-direction: column; }

.cc-row {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    min-height: 44px;
    padding: 11px 0;
    box-sizing: border-box;
    font-size: 15px;
    line-height: 1.45;
    color: $ink;
    cursor: pointer;
    input { width: 20px; height: 20px; margin: 0; accent-color: $hero; flex-shrink: 0; }
    b { color: $brown; font-weight: 700; }
}
.cc-all { font-weight: 700; border-bottom: 1px solid $line; }

.cc-list { margin: 0; padding: 0; list-style: none; }
.cc-line { display: flex; align-items: center; justify-content: space-between; gap: 8px; }

.cc-view {
    flex-shrink: 0;
    min-height: 44px;
    padding: 0 4px;
    border: 0;
    background: none;
    color: $sub;
    font-size: 13px;
    font-family: inherit;
    text-decoration: underline;
    cursor: pointer;
}

.cc-doc {
    max-height: 260px;
    overflow-y: auto;
    margin: 0 0 8px 30px;
    padding: 10px 0 10px 12px;
    border-left: 2px solid $line;
    font-size: 13px;
    line-height: 1.6;
    color: $sub;
    h4 { margin: 0 0 4px; font-size: 13px; color: $ink; }
    p { margin: 0 0 6px; word-break: keep-all; }
    .cc-doc-sec + .cc-doc-sec { margin-top: 10px; }
}

.cc-summary {
    margin: 0 0 12px;
    > div { display: flex; gap: 10px; padding: 4px 0; }
    dt { flex: 0 0 84px; color: $ink; font-weight: 600; }
    dd { margin: 0; flex: 1; min-width: 0; white-space: pre-line; word-break: keep-all; }
}
</style>
