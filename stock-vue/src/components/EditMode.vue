<template>
  <div class="edit-modal-overlay" @click.self="cancelEdit">
    <div class="edit-modal">
      <!-- 헤더 -->
      <div class="edit-header">
        <h3>그룹 관리</h3>
        <button class="add-group-button" @click="addGroup">+ 그룹 추가</button>
      </div>

      <!-- 드래그 앤 드롭 리스트 -->
      <draggable v-model="localGroups" handle=".drag-icon" animation="150">
        <template #item="{ element, index }">
          <div class="group-edit-item">
            <div class="group-info">
              <span class="drag-icon">≡</span>
              <input
                v-model="element.name"
                :disabled="!element.editable"
                class="group-name-input"
              />
            </div>
            <div class="edit-actions">
              <button
                v-if="element.editable"
                class="action-btn delete-btn"
                @click="removeGroup(index)"
              >
                삭제
              </button>
              <!-- 활성화 스위치 -->
              <label class="switch">
                <input type="checkbox" v-model="element.active" />
                <span class="slider"></span>
              </label>
            </div>
          </div>
        </template>
      </draggable>

      <!-- 푸터 -->
      <div class="edit-footer">
        <button class="cancel-btn" @click="cancelEdit">취소</button>
        <button class="apply-btn" @click="applyEdit">변경</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import draggable from 'vuedraggable'
import { ref, watch } from 'vue'

const props = defineProps({ groups: Array })
const emit = defineEmits(['close', 'apply'])

const localGroups = ref([...props.groups])

watch(
  () => props.groups,
  (val) => {
    localGroups.value = [...val]
  }
)

function addGroup() {
  localGroups.value.push({
    name: `새 그룹 ${localGroups.value.length + 1}`,
    editable: true,
    active: true
  })
}

function removeGroup(index) {
  localGroups.value.splice(index, 1)
}

function cancelEdit() {
  emit('close')
}

function applyEdit() {
  emit('apply', localGroups.value)
}
</script>

<style scoped>
.edit-modal-overlay {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  background-color: rgba(0, 0, 0, 0.6);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.edit-modal {
  background-color: #1e1f24;
  padding: 20px;
  border-radius: 12px;
  width: 92%;
  max-width: 420px;
  color: #fff;
}

.edit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.add-group-button {
  background: #4f46e5;
  color: white;
  border: none;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
}

.group-edit-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 4px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.group-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.drag-icon {
  cursor: grab;
  color: #aaa;
}

.group-name-input {
  background: transparent;
  border: none;
  color: white;
  font-size: 0.95rem;
  outline: none;
}

.edit-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-btn {
  background: transparent;
  border: 1px solid rgba(255,255,255,0.2);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  color: white;
  cursor: pointer;
}

.delete-btn {
  border-color: #e74c3c;
  color: #e74c3c;
}

.switch {
  position: relative;
  display: inline-block;
  width: 38px;
  height: 20px;
}
.switch input {
  opacity: 0;
  width: 0; height: 0;
}
.slider {
  position: absolute;
  cursor: pointer;
  top: 0; left: 0;
  right: 0; bottom: 0;
  background-color: #555;
  transition: 0.3s;
  border-radius: 20px;
}
.slider:before {
  position: absolute;
  content: "";
  height: 14px; width: 14px;
  left: 3px; bottom: 3px;
  background-color: white;
  border-radius: 50%;
  transition: 0.3s;
}
input:checked + .slider {
  background-color: #4f46e5;
}
input:checked + .slider:before {
  transform: translateX(18px);
}

.edit-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.cancel-btn,
.apply-btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 0.85rem;
  border: none;
  cursor: pointer;
}
.cancel-btn {
  background: #555;
  color: white;
}
.apply-btn {
  background: #4f46e5;
  color: white;
}
</style>
