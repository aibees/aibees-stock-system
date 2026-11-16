<template>
    <div id="stock-preset">
        <BrandHeader title="내 설정" back="/stock" />

        <main class="sp-main">
            <p class="sp-lead">회사를 고르는 보조지표를 켜고 끄고, 수치를 직접 고칠 수 있어요. 성향은 이 수치를 미리 정해 둔 묶음입니다.</p>

            <!-- ── 수치 묶음(preset) 불러오기: 누르면 아래 값이 바뀔 뿐, 저장은 맨 아래 버튼 ── -->
            <h2>성향으로 시작하기</h2>
            <ul class="sp-list" role="radiogroup" aria-label="성향 묶음">
                <li v-for="t in presets" :key="t.key">
                    <button type="button" role="radio" class="sp-row" :class="{ on: matchedPreset === t.key }"
                        :aria-checked="matchedPreset === t.key ? 'true' : 'false'" @click="loadPreset(t)">
                        <span class="sp-body">
                            <span class="sp-name">{{ t.name }}</span>
                            <span class="sp-desc">{{ t.desc }}</span>
                            <span class="sp-meta">{{ passRuleText(t.settings) }} · {{ orderLabel(t.settings.order) }}</span>
                        </span>
                        <span class="sp-check" aria-hidden="true">{{ matchedPreset === t.key ? '✓' : '' }}</span>
                    </button>
                </li>
            </ul>
            <p v-if="!matchedPreset" class="sp-custom-note">지금은 직접 고친 값이에요. 성향을 누르면 그 묶음의 수치로 되돌아갑니다.</p>

            <!-- ── 보조지표 ── -->
            <h2>보조지표</h2>
            <ul class="sp-ind-list">
                <li v-for="d in INDICATORS" :key="d.key" class="sp-ind" :class="{ off: !form[d.key].on }">
                    <button type="button" class="sp-ind-head" role="switch" :aria-checked="form[d.key].on ? 'true' : 'false'"
                        @click="form[d.key].on = !form[d.key].on">
                        <span class="sp-body">
                            <span class="sp-name">{{ d.label }}</span>
                            <span class="sp-desc">{{ d.desc }}</span>
                        </span>
                        <span class="sp-switch" :class="{ on: form[d.key].on }" aria-hidden="true">{{ form[d.key].on ? '사용' : '끔' }}</span>
                    </button>

                    <div v-if="form[d.key].on" class="sp-params">
                        <div v-for="p in d.params" :key="p.key" class="sp-param">
                            <span class="sp-plabel">{{ p.label }}</span>
                            <div class="sp-stepper">
                                <button type="button" class="sp-step" :aria-label="`${d.label} ${p.label} 줄이기`"
                                    :disabled="form[d.key][p.key] <= p.min" @click="bump(d.key, p, -1)">−</button>
                                <span class="sp-val"><b>{{ show(form[d.key][p.key]) }}</b>{{ p.unit }}</span>
                                <button type="button" class="sp-step" :aria-label="`${d.label} ${p.label} 늘리기`"
                                    :disabled="form[d.key][p.key] >= p.max" @click="bump(d.key, p, 1)">+</button>
                            </div>
                        </div>
                    </div>
                </li>
            </ul>

            <!-- ── 충족 기준 ── -->
            <h2>충족 기준</h2>
            <div class="sp-box">
                <div class="sp-stepper">
                    <button type="button" class="sp-step" aria-label="기준 줄이기" :disabled="form.minPass <= 1 || !onKeys.length" @click="form.minPass--">−</button>
                    <span class="sp-val">켜 둔 <b>{{ onKeys.length }}</b>개 중 <b>{{ Math.min(form.minPass, onKeys.length) }}</b>개 이상</span>
                    <button type="button" class="sp-step" aria-label="기준 늘리기" :disabled="form.minPass >= onKeys.length" @click="form.minPass++">+</button>
                </div>
                <p class="sp-hint">기준을 높일수록 조건에 꼭 맞는 회사만 남아 목록이 짧아집니다.</p>
            </div>

            <!-- ── 회사 순서 ── -->
            <h2>회사 순서</h2>
            <ul class="sp-list" role="radiogroup" aria-label="회사 순서">
                <li v-for="o in ORDER_OPTIONS" :key="o.key">
                    <button type="button" role="radio" class="sp-row sp-order" :class="{ on: form.order === o.key }"
                        :aria-checked="form.order === o.key ? 'true' : 'false'" @click="form.order = o.key">
                        <span class="sp-body">
                            <span class="sp-oname">{{ o.label }}</span>
                            <span class="sp-desc">{{ o.desc }}</span>
                        </span>
                        <span class="sp-check" aria-hidden="true">{{ form.order === o.key ? '✓' : '' }}</span>
                    </button>
                </li>
            </ul>

            <label v-if="!matchedPreset" class="sp-name-field">
                <span class="sp-label">이 설정의 이름</span>
                <input v-model="name" type="text" maxlength="10" placeholder="나만의 설정" autocomplete="off" />
            </label>

            <p class="sp-note">종목을 고르는 조건만 정합니다. 투자금이나 보유 종목 같은 개인 정보는 받지 않습니다. 직접 고친 값은 이 기기에만 저장돼요.</p>
            <p class="sp-note">이 조건은 서버가 먼저 추린 회사들 안에서 다시 걸러 보는 것이라, 조건을 넓혀도 목록에 없던 회사가 새로 나오진 않습니다.</p>
        </main>

        <footer class="sp-foot">
            <button type="button" class="sp-save" :disabled="!dirty" @click="save">{{ dirty ? '이 설정으로 저장' : '저장됨' }}</button>
        </footer>
    </div>
</template>

<script setup>
/**
 * 내 설정 — 보조지표를 켜고 끄고 수치를 고친다. 성향(preset)은 수치 묶음일 뿐이라 누르면 아래 값이 그 묶음으로 바뀐다.
 * 저장하면 persona 스토어의 현재 설정이 바뀌고 홈·매수추천·주식분석 대시보드가 그걸 따른다.
 * 값이 어느 성향과 같으면 그 성향으로, 다르면 "나만의 설정"(이 기기에만)으로 저장한다.
 */
import { usePersonaStore } from '@scripts/stores/persona-store.js';
import {
    INDICATORS, ORDER_OPTIONS, orderLabel, normalizeSettings, sameSettings, enabledKeys, passRuleText,
} from '@scripts/indicators.js';

const router = useRouter();
const persona = usePersonaStore();

const presets = computed(() => persona.presets);
const clone = (o) => JSON.parse(JSON.stringify(o));
const form = reactive(clone(persona.currentType.settings));
const name = ref(persona.custom?.name ?? '');
const onKeys = computed(() => enabledKeys(form));

// 켠 지표 수가 줄어 기준이 켜 둔 수보다 커지면 맞춘다
watch(onKeys, (keys) => { if (keys.length && form.minPass > keys.length) form.minPass = keys.length; });

const matchedPreset = computed(() => presets.value.find(t => sameSettings(t.settings, form))?.key ?? null);
const dirty = computed(() => !sameSettings(form, persona.currentType.settings)
    || (!matchedPreset.value && persona.currentType.key === 'custom' && name.value.trim() && name.value.trim() !== persona.currentType.name)
    || (!matchedPreset.value && persona.currentType.key !== 'custom'));

const show = (v) => (Number.isInteger(v) ? v.toLocaleString() : String(Math.round(v * 10) / 10));
const bump = (key, p, dir) => {
    const next = Math.round((form[key][p.key] + dir * p.step) * 100) / 100;
    form[key][p.key] = Math.min(p.max, Math.max(p.min, next));
};
const loadPreset = (t) => {
    Object.assign(form, clone(t.settings));
    name.value = '';
};

const save = () => {
    const settings = normalizeSettings(form);
    const hit = presets.value.find(t => sameSettings(t.settings, settings));
    if (hit) persona.decide(hit.key);
    else persona.decideCustom({ name: name.value, settings });
    router.push('/stock');
};
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#stock-preset {
    min-height: 100vh;
    background: $card;
    color: $ink;
    text-align: left;
    font-family: $font-body;
}
.sp-main { max-width: 720px; margin: 0 auto; padding: 14px 0 120px; }
.sp-lead { margin: 0 16px 4px; font-size: 14px; line-height: 1.5; color: $sub; word-break: keep-all; }
h2 { margin: 20px 16px 6px; font-size: 13px; font-weight: 700; color: $accent; }
.sp-list, .sp-ind-list { list-style: none; margin: 0; padding: 0; border-top: 1px solid $line-soft; }
.sp-list li, .sp-ind-list li { border-bottom: 1px solid $line-soft; }
.sp-row {
    width: 100%; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
    padding: 14px 16px; box-sizing: border-box; border: 0; background: transparent; color: inherit;
    font: inherit; text-align: left; cursor: pointer; -webkit-tap-highlight-color: transparent;
    @media (hover: hover) { &:hover { background: #FFFDF3; } }
    &.on { color: $brown-ink; }
    &.on .sp-name, &.on .sp-oname { font-weight: 800; }
    &.sp-order { padding: 12px 16px; }
}
.sp-body { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.sp-name { font-size: 16px; font-weight: 700; }
.sp-oname { font-size: 15px; font-weight: 600; }
.sp-desc { font-size: 13px; line-height: 1.45; color: $sub; word-break: keep-all; }
.sp-meta { font-size: 12px; color: $sub-2; }
.sp-check { flex: none; width: 20px; text-align: center; font-size: 18px; font-weight: 700; color: $accent; }
.sp-custom-note { margin: 8px 16px 0; font-size: 12px; color: $sub-2; }

.sp-ind { &.off .sp-name { color: $sub-2; font-weight: 600; } }
.sp-ind-head {
    width: 100%; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
    padding: 14px 16px; box-sizing: border-box; border: 0; background: transparent; color: inherit;
    font: inherit; text-align: left; cursor: pointer; -webkit-tap-highlight-color: transparent;
}
// 켜짐/꺼짐은 뱃지가 아니라 글자색으로만 구분한다
.sp-switch { flex: none; font-size: 13px; font-weight: 700; color: $sub-2; &.on { color: $accent; } }
.sp-params { padding: 0 16px 14px; display: flex; flex-direction: column; gap: 8px; }
.sp-param { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.sp-plabel { font-size: 13px; color: $sub; flex: none; min-width: 5.5em; }
.sp-stepper { flex: 1; display: flex; align-items: center; justify-content: space-between; gap: 8px; max-width: 280px; margin-left: auto; }
.sp-step {
    width: 40px; height: 40px; flex: none; border: 1px solid $line-2; border-radius: 10px; background: $card;
    color: $brown-ink; font-size: 20px; font-weight: 700; cursor: pointer;
    &:disabled { opacity: .3; cursor: default; }
}
.sp-val { font-size: 13px; color: $ink; text-align: center; b { font-size: 17px; font-weight: 800; margin-right: 2px; } }

.sp-box { margin: 0; padding: 12px 16px; border-top: 1px solid $line-soft; border-bottom: 1px solid $line-soft; .sp-stepper { max-width: none; } }
.sp-hint { margin: 8px 0 0; font-size: 12px; line-height: 1.5; color: $sub-2; }

.sp-name-field { display: flex; flex-direction: column; gap: 6px; margin: 18px 16px 0; }
.sp-label { font-size: 13px; font-weight: 700; }
.sp-name-field input {
    min-height: 44px; padding: 0 12px; box-sizing: border-box; border: 1px solid $line-2; border-radius: 10px;
    background: $card; color: $ink; font: inherit;
}
.sp-note { margin: 14px 16px 0; font-size: 12px; line-height: 1.6; color: $sub-2; word-break: keep-all; }

.sp-foot {
    position: fixed; left: 0; right: 0; bottom: var(--lnb-total, 0px);
    padding: 10px 16px; background: linear-gradient(to bottom, rgba(255, 255, 255, 0), $card 28%);
    z-index: 20; display: flex; justify-content: center;
}
.sp-save {
    width: 100%; max-width: 688px; min-height: 52px; border: 0; border-radius: 14px;
    background: $yellow; color: #3A200F; font: inherit; font-size: 16px; font-weight: 700; cursor: pointer;
    &:disabled { background: $line; color: $sub-2; cursor: default; }
}
</style>
