<template>
    <!-- 홈 = 간편 모드(기본) / 전문가 모드(기존 Home.vue, 동결 — 신규 기능을 넣지 않는다).
         모드는 성향 설정(persona-store)에 저장되고, 정하지 않았으면 매매 사용자는 전문가, 그 외는 간편으로 시작한다. -->
    <HomeExpert v-if="persona.effectiveMode === 'expert'" />
    <HomeSimple v-else />
</template>

<script setup>
import HomeExpert from '../Home.vue';
import HomeSimple from './HomeSimple.vue';
import { usePersonaStore } from '@scripts/stores/persona-store.js';

const persona = usePersonaStore();
</script>
