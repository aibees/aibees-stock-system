<template>
    <div class="auto-complete-container">
        <div class="search-bar">
            <div class="search-icon">🔍</div>
            
            <div class="label-badge" v-if="props.label">
                {{ props.label }}
            </div>

            <input  
                class="main-input"
                :id="`${props.id}`"
                type="text"
                v-model="typedData"
                @input="searchData"
                placeholder="종목명 입력..."
                autocomplete="off"
                :style="`text-align: ${setAlign()}`" />
            

            <button @click="$emit('search', typedCode)" class="search-btn">분석하기</button>
        </div>

        <div class="suggestion-div" v-show="!hiddenFlag">
            <ul class="suggestion-header">
                <li>
                    <div class="item s_code">코드</div>
                    <div class="item s_name">종목명</div>
                    <div class="item s_type">구분</div>
                </li>
            </ul>
            <ul class="suggestion-list">
                <li class="list-item" v-for="(data, idx) in optionList" :key="idx" @click="selectItem(data)">
                    <div class="item s_code">{{ data.stock_code }}</div>
                    <div class="item s_name">{{ data.stock_name }}</div>
                    <div class="item s_type">{{ data.type }}</div>
                </li>
            </ul>
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue';
import aibeesApi from '../../../scripts/aibeesApi.js'

const props = defineProps({
    id: String,
    label: String,
    size: String,
    width: String,
    align: String,
    autoSearch: Boolean
});

// Vue 3.4 이상에서 사용되는 defineModel
const typedData = defineModel('name');
const typedCode = defineModel('code');

// '분석하기' 버튼 클릭 시 부모 컴포넌트로 이벤트 전달을 위해 추가
defineEmits(['search']);

let debounceTimer = null;
const optionList = ref([]);
const hiddenFlag = ref(true);

const setAlign = () => {
    return props.align === undefined ? 'left' : props.align;
}

const searchData = async () => {
    if (typedData.value.length < 2) {
        hiddenFlag.value = true;
        return false;
    }

    hiddenFlag.value = false;

    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
        const param = {
            searchTxt: typedData.value
        }
        const { data } = await aibeesApi.get('/api/v1/stocks/search', { params: param });
        optionList.value = data.data;
        optionList.value.forEach(d => {
            d.type = d.stock_type_yf == 'KQ' ? '코스닥' : '코스피'
        });
    }, 300); // 300ms deBounce
}

const selectItem = async (data) => {
    hiddenFlag.value = true;
    typedData.value = data.stock_name;
    typedCode.value = data.stock_code;
}
</script>

<style lang="scss" scoped>
/* 테마에 맞는 컬러 변수 (프로젝트에 글로벌 변수가 있다면 교체하세요) */
$bg-card: #2a2d34;
$border-soft: #4a4d55;
$color-accent: #00e5ff;
$text-light: #ffffff;
$text-dark: #000000;
$hover-bg: rgba(0, 229, 255, 0.15);

.auto-complete-container {
    width: inherit;
    position: relative;
    margin: auto; // 가운데 정렬 유지

    .search-bar {
        // width: 80%;
        display: flex;
        align-items: center;
        background: $bg-card;
        margin: auto;
        padding: 6px 6px 6px 18px;
        border-radius: 16px;
        border: 1px solid $border-soft;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);

        .search-icon {
            font-size: 1.1rem;
            margin-right: 12px;
        }

        .label-badge {
            background-color: #52a703;
            color: white;
            padding: 4px 10px;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: 600;
            margin-right: 10px;
            white-space: nowrap;
        }

        input {
            background: transparent;
            border: none;
            color: $text-light;
            font-size: 1rem;
            font-weight: 500;

            &:focus {
                outline: none;
            }
            &::placeholder {
                color: #888;
            }
        }

        .main-input {
            flex: 1;
            height: 2.5rem;
            min-width: 100px;
        }

        .code-input {
            width: 55px;
            text-align: center;
            color: #aaa;
            font-size: 0.85rem;
            margin-right: 12px;
            border-left: 1px solid $border-soft;
            padding-left: 12px;
        }

        .search-btn {
            background: $color-accent;
            color: $text-dark;
            border: none;
            padding: 10px 20px;
            border-radius: 12px;
            font-weight: 800;
            cursor: pointer;
            transition: transform 0.2s;
            white-space: nowrap;

            &:active {
                transform: scale(0.95);
            }
        }
    }

    /* 드롭다운 UI 스타일링 */
    .suggestion-div {
        position: absolute;
        top: calc(100% + 10px); // 검색창 바로 아래에 띄움
        left: 0;
        width: 100%;
        background-color: $bg-card;
        border: 1px solid $border-soft;
        border-radius: 12px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        z-index: 999;
        overflow: hidden;

        ul {
            list-style: none;
            margin: 0;
            padding: 0;
        }

        li {
            display: flex;
            align-items: center;

            .item {
                padding: 10px 12px;
                font-size: 0.9rem;
            }

            .s_code {
                width: 70px;
                text-align: center;
                color: #000;
            }

            .s_name {
                flex: 1;
                text-align: left;
                color: #000;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            .s_type {
                width: 60px;
                text-align: center;
                color: #aaa;
            }
        }

        .suggestion-header {
            background-color: rgba(255, 255, 255, 0.05);
            border-bottom: 1px solid $border-soft;
            
            .item {
                font-weight: 700;
                color: #ccc;
            }
        }

        .suggestion-list {
            max-height: 250px;
            overflow-y: auto;

            /* 웹킷 기반 브라우저 스크롤바 디자인 */
            &::-webkit-scrollbar {
                width: 6px;
            }
            &::-webkit-scrollbar-thumb {
                background: #555;
                border-radius: 3px;
            }

            .list-item {
                transition: background-color 0.2s ease;

                &:hover {
                    background-color: $hover-bg;
                    cursor: pointer;
                }
            }
        }
    }
}
</style>