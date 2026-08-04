<!-- 
    메뉴 Template 최상단 잡아주는 Custom Div
 -->
<template>
    <div :class="setClassByType(props.type)">
        <slot />
    </div>
</template>

<script setup>
    const props = defineProps({
        type: String
    });

    const setClassByType = () => {
        if (props.type == 'web') {
            return 'body-for-web'
        } else if (props.type == 'mobile') {
            return 'body-for-mobile'
        }
    }
</script>

<style lang="scss" scoped>
.body-for-web {
    width: 70%;
    min-width: 1200px;
    max-width: 1800px;
    /* 넓은 화면에선 이 정도까지만 */
    margin: 1rem auto 1rem auto;
    padding: 0 1rem;
    font-size: 14px;
    box-sizing: border-box;
}


.body-for-mobile {
    width: 100%;
    max-width: 1200px;
    /* 넓은 화면에선 이 정도까지만 */
    margin: 1rem auto 1rem auto;
    padding: 0 1rem;
    font-size: 14px;
    box-sizing: border-box;
}
</style>