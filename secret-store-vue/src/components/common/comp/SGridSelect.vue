<template>
    <div class="custom-grid-select">
        <div class="label">
            {{ props.label }}
        </div>
        <select
            :id="`${props.id}`"
            v-model="typedData"
            :style="`text-align:${setAlign()}`"
        >
            <option v-for="opt in props.optionList" :key="opt.code" :value="opt.code">
                {{ opt.name }}
            </option>
        </select>
    </div>
</template>

<script setup>
    const props = defineProps({
        id: String,
        type: String,
        label: String,
        size: String,
        width: String,
        align: String,
        autoSearch: Boolean,
        optionList: Object
    });

    const typedData = defineModel();

    const setAlign = () => {
        if (props.align === undefined) {
            return 'left';
        } else {
            return props.align;
        }
    }
</script>

<style lang="scss" scoped>
.custom-grid-select{
    width: auto;
    display: flex;
    justify-content: space-between;
    height: 40px;
    margin: 20px auto 10px;
    font-size: 14px;
    font-weight: 600;

    .label {
        flex: 3;
        height:100%;
        padding: 3px 3px;
        text-align: left;
    }

    select {
        flex: 7;
        color: var(--sc-strong-text);
        height:100%;
        padding: 3px 10px;
        background-color: transparent;
        border: 1px solid var(--sc-border-strong);
        border-radius: 0;
        box-sizing: border-box;
        
        option {
            color: var(--sc-strong-text);
            background-color: var(--sc-strong-bg);
        }
    }
}
</style>