<template>
    <div id="support-licenses">
        <BrandHeader title="오픈소스 라이선스" back="/menu" />
        <main class="sp">
            <p class="lead">양봉상회는 아래 오픈소스 글꼴, 이미지, 라이브러리를 사용합니다. 각 저작권자에게 감사드립니다.</p>

            <section v-for="g in LICENSE_GROUPS" :key="g.title" class="group">
                <h2>{{ g.title }}</h2>
                <ul>
                    <li v-for="it in g.items" :key="it.name">
                        <b>{{ it.name }}</b>
                        <span class="by">{{ it.by }}</span>
                        <span v-if="it.note" class="note">{{ it.note }}</span>
                        <span class="meta">
                            <em>{{ it.license }}</em>
                            <a v-if="it.url" :href="it.url" target="_blank" rel="noopener">출처</a>
                            <button v-if="it.text" type="button" class="text-btn" @click="openText(it.text)">전문 보기</button>
                        </span>
                    </li>
                </ul>
            </section>
            <p class="foot">MIT License 전문: Permission is hereby granted, free of charge, to any person obtaining a copy of this software… 각 라이브러리의 저장소에서 확인할 수 있습니다.</p>
        </main>

        <div v-if="text.open" class="dim" @click.self="text.open = false">
            <section class="sheet" role="dialog" aria-modal="true" aria-label="라이선스 전문">
                <div class="sheet-head"><b>라이선스 전문</b><button type="button" class="close" aria-label="닫기" @click="text.open = false">×</button></div>
                <pre>{{ text.body || '불러오는 중이에요' }}</pre>
            </section>
        </div>
    </div>
</template>

<script setup>
import { LICENSE_GROUPS, LICENSE_TEXTS } from '@scripts/data/licenses.js';

const text = reactive({ open: false, body: '' });
const openText = async (key) => {
    text.open = true;
    text.body = '';
    try {
        const res = await fetch(LICENSE_TEXTS[key]);
        text.body = res.ok ? await res.text() : '전문을 불러오지 못했어요.';
    } catch {
        text.body = '전문을 불러오지 못했어요.';
    }
};
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#support-licenses { min-height: 100vh; background: $card; color: $ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; }
button { border: 0; background: transparent; color: inherit; font: inherit; cursor: pointer; }
.sp { max-width: 720px; margin: 0 auto; padding: 8px $pad-x 40px; box-sizing: border-box; }
.lead { margin: 4px 0 0; font-size: 14.5px; line-height: 1.6; color: $sub-ink; word-break: keep-all; }
.group { margin-top: 24px;
    h2 { margin: 0 0 4px; font-size: 13px; font-weight: 700; color: $sub; }
    ul { margin: 0; padding: 0; list-style: none; }
    li { padding: 14px 0; border-bottom: 1px solid $line; display: flex; flex-direction: column; gap: 3px; }
    b { font-size: 15.5px; word-break: keep-all; }
}
.by { font-size: 13px; color: $sub; }
.note { font-size: 13px; color: $sub-ink; }
.meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; margin-top: 4px; font-size: 13px;
    em { font-style: normal; padding: 3px 7px; border-radius: $radius-sm; background: $band; color: $sub-ink; font-weight: 600; }
    a, .text-btn { color: $amber-700; font-size: 13px; font-weight: 600; text-decoration: none; padding: 0; }
}
.foot { margin-top: 24px; font-size: 12.5px; line-height: 1.6; color: $sub; }
.dim { position: fixed; inset: 0; z-index: 1200; display: flex; align-items: flex-end; justify-content: center; background: rgba(25, 31, 40, .42); }
.sheet { width: 100%; max-width: 640px; max-height: 80vh; display: flex; flex-direction: column; box-sizing: border-box; padding: 16px 20px calc(16px + env(safe-area-inset-bottom, 0px)); border-radius: 16px 16px 0 0; background: $card;
    pre { flex: 1; overflow: auto; margin: 10px 0 0; padding: 12px; border-radius: $radius; background: $band; font-size: 11.5px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
}
.sheet-head { display: flex; justify-content: space-between; align-items: center; b { font-size: 16px; } }
.close { width: 36px; height: 36px; font-size: 24px; color: $sub; }
@media (min-width: 700px) { .dim { align-items: center; } .sheet { border-radius: 16px; } }
</style>
