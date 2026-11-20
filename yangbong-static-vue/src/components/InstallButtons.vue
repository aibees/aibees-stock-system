<template>
  <!-- 스토어 주소가 하나도 없을 때: 누를 수 없는 버튼 + 안내 -->
  <div v-if="!STORES.length" class="install" :class="{ center }">
    <span class="btn primary disabled" aria-disabled="true">앱 설치하기</span>
    <p class="soon">앱 출시를 준비하고 있어요.</p>
  </div>

  <!-- 휴대폰: 내 기기 스토어로 가는 버튼 하나(그 스토어가 없으면 있는 쪽으로) -->
  <div v-else-if="mine" class="install" :class="{ center }">
    <a class="btn primary" :href="mine.url" rel="noopener">앱 설치하기</a>
  </div>

  <!-- PC: 출시된 스토어를 모두 보여 준다 -->
  <div v-else class="install" :class="{ center }">
    <a v-for="s in STORES" :key="s.key" class="btn primary" :href="s.url" rel="noopener">{{ s.label }}에서 설치</a>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { STORES, detectPlatform } from '@/site.js';

defineProps({ center: { type: Boolean, default: false } });

const mine = ref(null);
onMounted(() => {
  const p = detectPlatform();
  if (p) mine.value = STORES.find((s) => s.key === p) || STORES[0];
});
</script>

<style scoped>
.install { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; }
.install.center { justify-content: center; }
.btn {
  display: inline-flex; align-items: center; justify-content: center;
  min-height: 50px; padding: 0 24px; border-radius: 12px;
  border: 1px solid var(--brand); background: var(--brand); color: #fff8e1;
  font-weight: 600; font-size: 16px; text-decoration: none;
  transition: transform .15s ease;
}
a.btn:active { transform: scale(.97); }
.btn.disabled { opacity: .45; cursor: default; }
.soon { margin: 0; color: var(--sub); font-size: 14px; }
@media (prefers-reduced-motion: reduce) { .btn { transition: none; } }
</style>
