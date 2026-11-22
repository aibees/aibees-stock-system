<template>
    <div id="stock-preset">
        <BrandHeader title="내 설정" back="/stock" />

        <main class="sp-main">

            <!-- ── 내 성향: 미리 정한 묶음. 바꾸는 화면은 따로 있다 ── -->
            <section class="sec" aria-labelledby="sp-persona-title">
                <div class="sec-head">
                    <h2 id="sp-persona-title">내 성향</h2>
                    <button type="button" class="sec-link" @click="router.push('/stock/persona')">바꾸기</button>
                </div>
                <div class="persona">
                    <b class="persona-name">{{ personaView.name }}</b>
                    <span class="persona-desc">{{ personaView.desc }}</span>
                </div>
            </section>

            <!-- ── 보조지표 설정: 성향과 별개로 직접 고치는 값 ── -->
            <section class="sec" aria-labelledby="sp-ind-title">
                <h2 id="sp-ind-title">보조지표 설정</h2>
                <p class="sub">회사를 고르는 조건을 직접 켜고 끄고 고쳐요.</p>

                <ul class="ind-list">
                    <li v-for="d in BASIC_INDICATORS" :key="d.key" class="ind"
                        :class="{ off: !form[d.key].on, locked: !unlocked(d) }">
                        <div class="ind-fade" :aria-disabled="!unlocked(d) ? 'true' : undefined">
                            <button type="button" class="ind-head" role="switch" :aria-checked="form[d.key].on ? 'true' : 'false'"
                                :disabled="!unlocked(d)" @click="form[d.key].on = !form[d.key].on">
                                <span class="body">
                                    <span class="name">{{ d.label }}</span>
                                    <span class="desc">{{ d.desc }}</span>
                                </span>
                                <span class="toggle" :class="{ on: form[d.key].on }" aria-hidden="true"><i></i></span>
                            </button>

                            <div v-if="form[d.key].on && unlocked(d)" class="params">
                                <div v-for="p in d.params" :key="p.key" class="param">
                                    <span class="plabel">{{ p.label }}</span>
                                    <div class="stepper">
                                        <button type="button" class="step" :aria-label="`${d.label} ${p.label} 줄이기`"
                                            :disabled="atEdge(form[d.key][p.key], p, -1)" @click="bump(d.key, p, -1)">−</button>
                                        <span class="val"><b>{{ show(form[d.key][p.key]) }}</b>{{ p.unit }}</span>
                                        <button type="button" class="step" :aria-label="`${d.label} ${p.label} 늘리기`"
                                            :disabled="atEdge(form[d.key][p.key], p, 1)" @click="bump(d.key, p, 1)">+</button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- 잠금 안내는 반투명 밖에 둬서 또렷하게 읽히고 누를 수 있게 한다 -->
                        <p v-if="!unlocked(d)" class="lock">
                            <template v-if="lessonOf(d)">
                                트레이닝 <button type="button" class="lock-link" @click="router.push(stagePath(lessonOf(d)))">‘{{ lessonOf(d).short }}’</button> 단계를 마치면 열려요.
                            </template>
                            <template v-else>트레이닝을 준비하고 있어요.</template>
                        </p>
                    </li>
                </ul>
            </section>

            <!-- ── 충족 기준 ── -->
            <section class="sec" aria-labelledby="sp-rule-title">
                <h2 id="sp-rule-title">충족 기준</h2>
                <div class="stepper wide">
                    <button type="button" class="step" aria-label="기준 줄이기" :disabled="form.minPass <= 1 || !onKeys.length" @click="form.minPass--">−</button>
                    <span class="val">켜 둔 <b>{{ onKeys.length }}</b>개 중 <b>{{ Math.min(form.minPass, onKeys.length) }}</b>개 이상</span>
                    <button type="button" class="step" aria-label="기준 늘리기" :disabled="form.minPass >= onKeys.length" @click="form.minPass++">+</button>
                </div>
            </section>

            <!-- ── 회사 순서 ── -->
            <section class="sec" aria-labelledby="sp-order-title">
                <h2 id="sp-order-title">회사 순서</h2>
                <ul class="rows" role="radiogroup" aria-label="회사 순서">
                    <li v-for="o in ORDER_OPTIONS" :key="o.key">
                        <button type="button" role="radio" class="row" :class="{ on: form.order === o.key }"
                            :aria-checked="form.order === o.key ? 'true' : 'false'" @click="form.order = o.key">
                            <span class="body">
                                <span class="oname">{{ o.label }}</span>
                                <span class="desc">{{ o.desc }}</span>
                            </span>
                            <span class="radio" :class="{ on: form.order === o.key }" aria-hidden="true"></span>
                        </button>
                    </li>
                </ul>
            </section>

            <!-- ── 프리미엄 지표: 준비 중이라 이름만 ── -->
            <section class="sec" aria-labelledby="sp-prem-title">
                <h2 id="sp-prem-title">프리미엄 지표</h2>
                <ul class="prem">
                    <li v-for="d in PREMIUM_INDICATORS" :key="d.key"><span>{{ d.label }}</span><em>준비 중</em></li>
                </ul>
            </section>

            <!-- ── 직접 고친 값이면 이름을 붙인다 ── -->
            <section v-if="!matchedPreset" class="sec" aria-labelledby="sp-name-title">
                <h2 id="sp-name-title">설정 이름</h2>
                <input v-model="name" class="name-input" type="text" maxlength="10" placeholder="나만의 설정" autocomplete="off" aria-label="설정 이름" />
            </section>
        </main>

        <footer class="foot">
            <button type="button" class="save" :disabled="!dirty" @click="save">{{ dirty ? '저장' : '저장됨' }}</button>
        </footer>
    </div>
</template>

<script setup>
/**
 * 내 설정 — 보조지표를 켜고 끄고 수치를 고친다(2026-11-22 홈 톤으로 개편).
 * 성향(preset)은 수치를 미리 정해 둔 묶음이라 고르는 화면을 따로 뒀다(/stock/persona). 여기서는 지금 성향만 보여 주고 바꾸러 가는 길만 연다.
 * 저장하면 persona 스토어의 현재 설정이 바뀌고 홈·매수추천·주식분석 대시보드가 그걸 따른다.
 * 값이 어느 성향과 같으면 그 성향으로, 다르면 "나만의 설정"(이 기기에만)으로 저장한다.
 */
import { usePersonaStore } from '@scripts/stores/persona-store.js';
import { useTrainingStore } from '@scripts/stores/training-store.js';
import { allStages, stagePath } from '@scripts/training.js';
import {
    BASIC_INDICATORS, PREMIUM_INDICATORS, ORDER_OPTIONS, normalizeSettings, sameSettings, enabledKeys,
} from '@scripts/indicators.js';

const router = useRouter();
const persona = usePersonaStore();

const training = useTrainingStore();

const presets = computed(() => persona.presets);
// 저장된 값에 프리미엄이 켜져 있거나(개편 전 저장분) 범위 밖 값이 있어도 화면은 바로잡은 값으로 시작한다
const form = reactive(normalizeSettings(persona.currentType.settings));

/* ── 기본 지표 잠금: 지표의 트레이닝 단계(lesson)를 마쳤으면 연다 ── */
const lessonOf = (d) => (d.lesson ? allStages().find(s => s.key === d.lesson) ?? null : null);
const unlocked = (d) => !!lessonOf(d) && training.isDone(d.lesson);
const name = ref(persona.custom?.name ?? '');
const onKeys = computed(() => enabledKeys(form));

// 켠 지표 수가 줄어 기준이 켜 둔 수보다 커지면 맞춘다
watch(onKeys, (keys) => { if (keys.length && form.minPass > keys.length) form.minPass = keys.length; });

const matchedPreset = computed(() => presets.value.find(t => sameSettings(t.settings, form))?.key ?? null);
// 지금 보여 줄 성향: 값이 어느 성향과 같으면 그 성향, 아니면 직접 고친 값
const personaView = computed(() => {
    const hit = presets.value.find(t => t.key === matchedPreset.value);
    if (hit) return { name: hit.name, desc: hit.desc };
    return { name: name.value.trim() || persona.custom?.name || '나만의 설정', desc: '직접 고친 값이에요.' };
});
const dirty = computed(() => !sameSettings(form, persona.currentType.settings)
    || (!matchedPreset.value && persona.currentType.key === 'custom' && name.value.trim() && name.value.trim() !== persona.currentType.name)
    || (!matchedPreset.value && persona.currentType.key !== 'custom'));

const show = (v) => (Number.isInteger(v) ? v.toLocaleString() : String(Math.round(v * 10) / 10));
// choices 가 있는 수치(이평선 5·20·60)는 선택지 사이를 오간다
const atEdge = (v, p, dir) => (p.choices
    ? (dir < 0 ? v <= p.choices[0] : v >= p.choices.at(-1))
    : (dir < 0 ? v <= p.min : v >= p.max));
const bump = (key, p, dir) => {
    const v = form[key][p.key];
    if (p.choices) {
        const i = p.choices.indexOf(v);
        const next = p.choices[Math.min(p.choices.length - 1, Math.max(0, (i < 0 ? 0 : i) + dir))];
        form[key][p.key] = next;
        return;
    }
    const next = Math.round((v + dir * p.step) * 100) / 100;
    form[key][p.key] = Math.min(p.max, Math.max(p.min, next));
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

/* 홈과 같은 구조: 연회색 바탕 위에 흰 판을 띠 간격으로 쌓는다. 제목 20 / 항목 16 / 설명 13(회색). */
#stock-preset {
    min-height: 100vh;
    background: $band;
    color: $ink;
    text-align: left;
    font-family: $font-body;
    letter-spacing: -0.2px;
    -webkit-font-smoothing: antialiased;
}
.sp-main { max-width: 640px; margin: 0 auto; padding-bottom: 120px; display: flex; flex-direction: column; gap: $band-h; }
.sec { background: $card; padding: 28px $pad-x 20px; }
.sec-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
h2 { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
.sub { margin: 6px 0 0; font-size: 13px; color: $sub; }
.sec-link {
    min-height: 32px; padding: 0; border: 0; background: transparent; color: $sub; font: inherit; font-size: 13px; cursor: pointer;
    &::after { content: ' ›'; color: $sub-2; }
}

/* 내 성향 */
.persona { margin-top: 12px; padding: 14px 16px; border-radius: $radius; background: $honey-strip; display: flex; flex-direction: column; gap: 4px; }
.persona-name { font-size: 17px; font-weight: 700; }
.persona-desc { font-size: 14px; color: $sub-ink; word-break: keep-all; }

/* 목록 공통 */
.body { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.name { font-size: 16px; font-weight: 600; }
.oname { font-size: 16px; font-weight: 600; }
.desc { font-size: 13px; line-height: 1.45; color: $sub; word-break: keep-all; }

.ind-list, .rows, .prem { list-style: none; margin: 8px 0 0; padding: 0; }
.ind { &.off .name { color: $sub-2; } }
.ind-head, .row {
    width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 64px;
    padding: 10px 0; box-sizing: border-box; border: 0; background: transparent; color: inherit;
    font: inherit; text-align: left; cursor: pointer; -webkit-tap-highlight-color: transparent;
}
// 잠긴 지표: 반투명 + 누를 수 없음. 잠금 안내 한 줄만 또렷하게
.ind.locked .ind-fade { opacity: .42; }
.ind.locked .ind-head { cursor: default; }
.lock { margin: -4px 0 8px; font-size: 12px; line-height: 1.5; color: $sub-ink; word-break: keep-all; }
.lock-link { padding: 0; border: 0; background: none; color: $amber-700; font: inherit; font-weight: 700; text-decoration: underline; text-underline-offset: 2px; cursor: pointer; }

// 켜짐/꺼짐 스위치
.toggle {
    flex: none; position: relative; width: 44px; height: 26px; border-radius: 13px; background: $line; transition: background .15s;
    i { position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 10px; background: $card; box-shadow: 0 1px 2px rgba(0, 0, 0, .18); transition: transform .15s; }
    &.on { background: $honey-500; i { transform: translateX(18px); } }
}
@media (prefers-reduced-motion: reduce) { .toggle, .toggle i { transition: none; } }

.params { padding: 0 0 12px; display: flex; flex-direction: column; gap: 8px; }
.param { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.plabel { font-size: 13px; color: $sub; flex: none; min-width: 5.5em; }
.stepper { flex: 1; display: flex; align-items: center; justify-content: space-between; gap: 8px; max-width: 280px; margin-left: auto; &.wide { max-width: none; margin-top: 12px; } }
.step {
    width: 40px; height: 40px; flex: none; border: 1px solid $line; border-radius: 10px; background: $card;
    color: $ink; font-size: 20px; font-weight: 700; cursor: pointer;
    &:disabled { opacity: .3; cursor: default; }
}
.val { font-size: 13px; color: $ink; text-align: center; b { font-size: 17px; font-weight: 800; margin-right: 2px; } }

.radio {
    flex: none; width: 22px; height: 22px; border-radius: 11px; border: 2px solid $sub-2; box-sizing: border-box;
    &.on { border-color: $honey-500; background: $honey-500; box-shadow: inset 0 0 0 4px $card; }
}

.prem li { display: flex; align-items: center; justify-content: space-between; min-height: 48px; font-size: 16px; color: $sub-2; em { font-style: normal; font-size: 13px; font-weight: 700; color: $sub; } }

.name-input {
    width: 100%; min-height: 48px; margin-top: 12px; padding: 0 12px; box-sizing: border-box;
    border: 1px solid $line; border-radius: 10px; background: $card; color: $ink; font: inherit;
}

.foot {
    position: fixed; left: 0; right: 0; bottom: var(--lnb-total, 0px);
    padding: 10px $pad-x; background: linear-gradient(to bottom, rgba(255, 255, 255, 0), $card 28%);
    z-index: 20; display: flex; justify-content: center;
}
.save {
    width: 100%; max-width: 600px; min-height: 52px; border: 0; border-radius: $radius;
    background: $honey-300; color: $honey-ink; font: inherit; font-size: 16px; font-weight: 700; cursor: pointer;
    &:disabled { background: $band; color: $sub-2; cursor: default; }
}
</style>
