// 차트 분석 레이어 표시 ON/OFF — 사용자별(이 브라우저) 기억.
// 어떤 레이어를 "계산할지"는 서버 공통코드(screen/CHART_ANALYSIS)가 정하고, 여기서는 받은 것 중 "보일지"만 정한다.
import { ref } from 'vue'
import { LAYERS } from './layers.js'

const STORAGE_KEY = 'chartLayers.v1'
const DEFAULT_ON = LAYERS.map(l => l.key)

const load = () => {
    try {
        const v = JSON.parse(localStorage.getItem(STORAGE_KEY))
        return Array.isArray(v) ? v : DEFAULT_ON
    } catch {
        return DEFAULT_ON
    }
}

const enabled = ref(load())

export function useChartLayers() {
    const isOn = (key) => enabled.value.includes(key)
    const toggle = (key) => {
        enabled.value = isOn(key) ? enabled.value.filter(k => k !== key) : [...enabled.value, key]
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(enabled.value)) } catch { /* 저장 못 해도 이번 화면에서는 동작 */ }
    }
    return { enabled, isOn, toggle }
}
