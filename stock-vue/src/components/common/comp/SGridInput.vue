<template>
    <div class="custom-grid-input">
        <div class="label">
            {{ props.label }}
        </div>
        <input 
            :id="`${props.id}`"
            :type="`${setType()}`" 
            v-model="typedData"
            :style="`text-align:${setAlign()}`"
            :readonly="props.readonly"
        />
    </div>
</template>

<script setup>
const props = defineProps({
    id: String,
    type: String,
    label: String,
    size: String,
    align: String,
    autoSearch: Boolean,
    readonly: Boolean
});

const typedData = defineModel();

const setType = () => {
    if (props.type === undefined) {
        return 'text';
    } else {
        return props.type;
    }
}

const setAlign = () => {
    if (props.align === undefined) {
        return 'left';
    } else {
        return props.align;
    }
}

</script>

<style lang="scss" scoped>
.custom-grid-input{
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

    input {
        flex: 7;
        color: white;
        height:100%;
        padding: 3px 10px;
        background-color: transparent;
        border: 1px solid #cbcbcba1;
        border-radius: 8px;
        
        box-sizing: border-box;
    }
}

</style>