// 차트 분석 레이어 표시 ON/OFF — 사용자별(이 브라우저) 기억.
// 어떤 레이어를 "계산할지"는 서버 공통코드(screen/CHART_ANALYSIS)가 정하고, 여기서는 받은 것 중 "보일지"만 정한다.
// 끈 레이어만 저장한다 — 나중에 레이어가 새로 생기면 기본으로 켜져 보이게.
import { ref, computed } from 'vue'
import { LAYERS } from './layers.js'

const STORAGE_KEY = 'chartLayersOff.v1'

const load = () => {
    try {
        const v = JSON.parse(localStorage.getItem(STORAGE_KEY))
        return Array.isArray(v) ? v : []
    } catch {
        return []
    }
}

const off = ref(load())
const enabled = computed(() => LAYERS.map(l => l.key).filter(k => !off.value.includes(k)))

export function useChartLayers() {
    const isOn = (key) => !off.value.includes(key)
    const toggle = (key) => {
        off.value = isOn(key) ? [...off.value, key] : off.value.filter(k => k !== key)
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(off.value)) } catch { /* 저장 못 해도 이번 화면에서는 동작 */ }
    }
    return { enabled, isOn, toggle }
}
