<template>
    <div id="support-licenses">
        <BrandHeader title="오픈소스 라이선스" back="/menu" />
        <main class="sp">
            <p class="lead">양봉상회는 아래 오픈소스 글꼴, 이미지, 라이브러리를 사용합니다. 각 저작권자에게 감사드립니다.</p>

            <!-- 2026-11-22 출처·전문 보기 버튼은 뺐다(이름·저작권자·라이선스 이름만). 라이선스 원문 파일은 앱 안(public)에 그대로 둔다. -->
            <section v-for="g in LICENSE_GROUPS" :key="g.title" class="group">
                <h2>{{ g.title }}</h2>
                <ul>
                    <li v-for="it in g.items" :key="it.name">
                        <b>{{ it.name }}</b>
                        <span class="by">{{ it.by }}</span>
                        <span v-if="it.note" class="note">{{ it.note }}</span>
                        <span class="meta"><em>{{ it.license }}</em></span>
                    </li>
                </ul>
            </section>
            <p class="foot">MIT License 전문: Permission is hereby granted, free of charge, to any person obtaining a copy of this software… 각 라이브러리의 저장소에서 확인할 수 있습니다.</p>
        </main>
    </div>
</template>

<script setup>
import { LICENSE_GROUPS } from '@scripts/data/licenses.js';
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#support-licenses { min-height: 100vh; background: $card; color: $ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; }
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
}
.foot { margin-top: 24px; font-size: 12.5px; line-height: 1.6; color: $sub; }
</style>
