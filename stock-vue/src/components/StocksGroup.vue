<template>
  <div>
    <Headers :prop_title="title" />

    <!-- Tab bar + 편집 버튼 -->
    <div class="tab-bar-wrapper">
      <div class="tab-bar" ref="tabScroll">
        <div
          v-for="(tab, index) in tabs"
          :key="tab.id"
          :class="['tab-item', { active: currentTab === index }]"
          @click="selectTab(index)"
          :ref="el => tabRefs[index] = el"
        >
          {{ tab.name }}
        </div>
        <div class="tab-indicator" :style="indicatorStyle"></div>
      </div>

      <!-- 편집 버튼 -->
      <div class="tab-bar-fade">
        <button class="edit-button" @click="enterEditMode">편집</button>
      </div>
    </div>

      <!-- 팝업 편집 모드 (모달) -->
    <EditModal
  v-if="editMode"
  :groups="[...groups]"  
  @close="editMode = false"
  @apply="updateGroups"
/>
    <!-- 기본 콘텐츠 -->
    <div v-else class="tab-content">
      <template v-if="isGroupTab">
        <div v-if="currentGroupStocks.length" class="stock-list">
          <div
            v-for="stock in currentGroupStocks"
            :key="stock.code"
            class="stock-item"
          >
            {{ stock.name }} ({{ stock.code }})
          </div>
        </div>
        <div v-else class="group-empty">
          등록된 관심종목이 없습니다.
        </div>
        <button class="add-button">종목추가</button>
      </template>

      <template v-else>
        <div class="group-empty">해당 탭은 준비 중입니다.</div>
      </template>
    </div>
  </div>
</template>


<script setup>
import Lnb from './common/Lnb.vue'
import { ref, onMounted, nextTick, computed, watch } from 'vue'
import EditModal from '@/components/EditMode.vue';
const title = '관심종목'
const editMode = ref(false) // ✨ 편집 모드

const tabs = ref([
  { id: 1, name: '최근조회', type: 'default' },
  { id: 2, name: '배당주', type: 'group' },
  { id: 3, name: 'AI 테마', type: 'group' }
])

const groups = ref([
  { name: '보유종목', editable: false, active: true },
  { name: '최근조회', editable: false, active: true },
  { name: '주목', editable: true, active: true }
])

const currentTab = ref(0)
const tabRefs = ref([])
const indicatorStyle = ref({})

function selectTab(index) {
  currentTab.value = index
}

function updateGroups(newGroups) {
  // 그룹 배열 업데이트
  groups.value = newGroups

  // tabs 도 업데이트 (active = true 인 것만 탭에 표시)
  tabs.value = newGroups
    .filter(g => g.active)
    .map((g, idx) => ({
      id: idx + 1,
      name: g.name,
      type: 'group'
    }))

  // 첫 번째 탭으로 이동
  currentTab.value = 0
  updateIndicator()
}

function updateIndicator() {
  nextTick(() => {
    const el = tabRefs.value[currentTab.value]
    if (el) {
      indicatorStyle.value = {
        left: `${el.offsetLeft}px`,
        width: `${el.offsetWidth}px`
      }
    }
  })
}

onMounted(() => {
  updateIndicator()
})

watch(currentTab, () => {
  updateIndicator()
})

const isGroupTab = computed(() => tabs.value[currentTab.value]?.type === 'group')

// 그룹 종목 (예시)
const currentGroupStocks = computed(() => {
  const tabName = tabs.value[currentTab.value]?.name
  return [] // 생략 가능
})

// ✨ 편집 버튼 클릭 시
function enterEditMode() {
  editMode.value = true
}
function cancelEdit() {
  editMode.value = false
}
function applyEdit() {
  // TODO: 실제 변경 적용
  editMode.value = false
}
</script>

<style src="@@/comm/Groups.scss" scoped></style>
