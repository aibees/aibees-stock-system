<template>
    <div id="stock-persona">
        <BrandHeader title="내 성향" back="/stock/preset" />

        <main class="sp-main">
            <section class="sec" aria-labelledby="persona-title">
                <h2 id="persona-title">성향 고르기</h2>
                <p class="sub">고르면 보조지표 수치가 그 성향의 값으로 바뀌어요.</p>

                <ul class="rows" role="radiogroup" aria-label="성향">
                    <li v-for="t in types" :key="t.key">
                        <button type="button" role="radio" class="row" :class="{ on: chosen === t.key }"
                            :aria-checked="chosen === t.key ? 'true' : 'false'" @click="chosen = t.key">
                            <span class="body">
                                <span class="name">{{ t.name }}<em v-if="t.key === persona.currentType.key">지금 성향</em></span>
                                <span class="desc">{{ t.desc }}</span>
                            </span>
                            <span class="radio" :class="{ on: chosen === t.key }" aria-hidden="true"></span>
                        </button>
                    </li>
                </ul>
            </section>
        </main>

        <footer class="foot">
            <button type="button" class="save" :disabled="!dirty" @click="confirm">{{ dirty ? '이 성향으로 바꾸기' : '지금 성향이에요' }}</button>
        </footer>
    </div>
</template>

<script setup>
/**
 * 성향 변경 화면(2026-11-22 내 설정 개편에서 분리).
 * 성향은 보조지표 수치를 미리 정해 둔 묶음이라, 바꾸면 내 설정의 수치가 그 값으로 돌아간다. 수치를 직접 고치는 건 내 설정 화면.
 * 직접 고친 값(나만의 설정)이 있으면 그것도 고를 수 있다.
 */
import { usePersonaStore } from '@scripts/stores/persona-store.js';
import { CUSTOM_KEY } from '@scripts/persona.js';

const router = useRouter();
const persona = usePersonaStore();

const types = computed(() => {
    const list = persona.presets.map(t => ({ key: t.key, name: t.name, desc: t.desc }));
    if (persona.custom) list.push({ key: CUSTOM_KEY, name: persona.custom.name, desc: '직접 고쳐 둔 값이에요.' });
    return list;
});

const chosen = ref(persona.currentType.key);
const dirty = computed(() => chosen.value !== persona.currentType.key);

const confirm = () => {
    if (chosen.value === CUSTOM_KEY) persona.decideCustom(persona.custom);
    else persona.decide(chosen.value);
    router.replace('/stock/preset');
};
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#stock-persona {
    min-height: 100vh;
    background: $band;
    color: $ink;
    text-align: left;
    font-family: $font-body;
    letter-spacing: -0.2px;
}
.sp-main { max-width: 640px; margin: 0 auto; padding-bottom: 120px; }
.sec { background: $card; padding: 28px $pad-x 12px; }
h2 { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
.sub { margin: 6px 0 0; font-size: 13px; color: $sub; }

.rows { list-style: none; margin: 12px 0 0; padding: 0; }
.row {
    width: 100%;
    min-height: 72px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 0;
    box-sizing: border-box;
    border: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
}
.body { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.name { font-size: 17px; font-weight: 700; em { margin-left: 8px; font-style: normal; font-size: 12px; font-weight: 700; color: $amber-700; } }
.desc { font-size: 14px; line-height: 1.45; color: $sub; word-break: keep-all; }
.radio {
    flex: none;
    width: 22px;
    height: 22px;
    border-radius: 11px;
    border: 2px solid $sub-2;
    box-sizing: border-box;
    &.on { border-color: $honey-500; background: $honey-500; box-shadow: inset 0 0 0 4px $card; }
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
