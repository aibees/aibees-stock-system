<template>
    <div class="area-div" :class="setDivClass()">
        <slot />
    </div>
</template>

<script setup>

    const props = defineProps({
        flex: Boolean,
        scroll: Boolean
    });

    const setDivClass = () => {
        let classStr = 'area-div';
        if (props.flex) {
            classStr = classStr.concat(' flex-option');
        }

        if (props.scroll) {
            classStr = classStr.concat(' scroll-option');
        }
        return classStr;
    }
</script>

<style lang="scss" scoped>
.area-div {

    background-color: #2c2c2c;
    color: #fafafa;
    /* 밝고 부드러운 회색 계열 배경 */
    border-radius: 10px;
    padding: 1rem 1.5rem;
    // color: #333;
    /* 다크 그레이 */

    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
    box-sizing: border-box;
    margin: 15px 10px;
}

.flex-option {
    display: flex;
    justify-content: center;
    gap: 1rem;
    /* 기본은 가로 정렬 */
    flex-direction: row;
}

.scroll-option {
    overflow-y: scroll;
}
</style>