<template>
  <main class="doc wrap">
    <h1>서비스 이용약관</h1>
    <p class="meta">시행일: {{ TERMS_VERSION }}</p>
    <section v-for="s in TERMS_SECTIONS" :key="s.title">
      <h2>{{ s.title }}</h2>
      <ol v-if="s.body.length > 1">
        <li v-for="(line, i) in s.body" :key="i">{{ line }}</li>
      </ol>
      <p v-else>{{ s.body[0] }}</p>
    </section>
    <p v-for="line in OPERATOR_INFO" :key="line" class="meta">{{ line }}</p>
  </main>
</template>

<script setup>
// 앱 가입 화면에서 동의받는 약관과 같은 문구(data/termsOfService.js 는 앱 원본의 사본).
import { TERMS_VERSION, TERMS_SECTIONS, OPERATOR_INFO } from '@/data/termsOfService.js';
</script>
