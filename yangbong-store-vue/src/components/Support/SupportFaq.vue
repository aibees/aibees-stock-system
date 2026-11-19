<template>
    <div id="support-faq">
        <BrandHeader title="자주 묻는 질문" back="/menu" />
        <main class="sp">
            <div class="chips" role="group" aria-label="질문 분류">
                <button v-for="c in tabs" :key="c.key" type="button" class="chip" :class="{ on: active === c.key }"
                    :aria-pressed="active === c.key ? 'true' : 'false'" @click="active = c.key">{{ c.name }}</button>
            </div>

            <section v-for="c in shown" :key="c.key" class="group" :aria-labelledby="`faq-${c.key}`">
                <h2 :id="`faq-${c.key}`">{{ c.name }}</h2>
                <ul>
                    <li v-for="(f, i) in c.items" :key="i">
                        <button type="button" class="q" :aria-expanded="open === `${c.key}-${i}` ? 'true' : 'false'"
                            @click="toggle(`${c.key}-${i}`)">
                            <span>{{ f.q }}</span>
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"></path></svg>
                        </button>
                        <p v-if="open === `${c.key}-${i}`" class="a">{{ f.a }}</p>
                    </li>
                </ul>
            </section>

            <section class="ask">
                <p>원하는 답을 찾지 못하셨나요?</p>
                <button type="button" @click="router.push(CONTACT_PATH)">문의하기</button>
            </section>
        </main>
    </div>
</template>

<script setup>
import faq from '@scripts/data/faq.json';
import { CONTACT_PATH } from '@scripts/support.js';

const router = useRouter();
const tabs = [{ key: 'all', name: '전체' }, ...faq.categories];
const active = ref('all');
const open = ref(null);
const shown = computed(() => (active.value === 'all' ? faq.categories : faq.categories.filter(c => c.key === active.value)));
const toggle = (id) => { open.value = open.value === id ? null : id; };
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#support-faq { min-height: 100vh; background: $card; color: $ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; }
button { border: 0; background: transparent; color: inherit; font: inherit; letter-spacing: inherit; cursor: pointer; }
.sp { max-width: 720px; margin: 0 auto; padding: 4px $pad-x 32px; box-sizing: border-box; }
.chips { display: flex; gap: 6px; overflow-x: auto; padding: 6px 0 4px; scrollbar-width: none; &::-webkit-scrollbar { display: none; } }
.chip { flex: none; height: 34px; padding: 0 13px; border-radius: 17px; background: $band; color: $sub-ink; font-size: 14px; font-weight: 600;
    &.on { background: $ink; color: #fff; } }
.group { margin-top: 22px; h2 { margin: 0 0 4px; font-size: 13px; font-weight: 700; color: $sub; } ul { margin: 0; padding: 0; list-style: none; } li { border-bottom: 1px solid $line; } }
.q { width: 100%; min-height: 56px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 0; text-align: left; font-size: 16px; font-weight: 600; word-break: keep-all;
    svg { flex: none; width: 18px; height: 18px; fill: none; stroke: $sub-2; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; transition: transform .15s; }
    &[aria-expanded='true'] svg { transform: rotate(180deg); } }
.a { margin: 0 0 14px; padding: 12px 14px; border-radius: $radius; background: $band; color: $sub-ink; font-size: 14.5px; line-height: 1.6; word-break: keep-all; }
.ask { margin-top: 28px; padding: 18px; border-radius: $radius; background: $honey-strip; text-align: center;
    p { margin: 0; font-size: 14px; color: $honey-ink; }
    button { margin-top: 10px; height: 44px; padding: 0 22px; border-radius: $radius; background: #5A3C08; color: #fff; font-size: 15px; font-weight: 700; } }
</style>
