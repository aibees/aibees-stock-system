<template>
    <div class="maria-label-input" >
        <div class="labels" :hidden="props.label === '' || props.label === undefined">{{ props.label }}</div>
        <input 
            :id="`${props.id}`"
            :type="`${setType()}`" 
            v-model="typedData"
            :style="`width:${setWidth()}; text-align:${setAlign()}`" />
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
    autoSearch: Boolean
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

const setWidth = () => {
    if (props.width !== undefined) {
        return props.width;
    } else {
        if (props.size === undefined) {
            return '250px';
        } else if (props.size === 'lg') {
            return '350px';
        } else if (props.size === 'md') {
            return '300px';
        } else if (props.size === 'sm') {
            return '250px';
        } else {
            return '90%';
        }
    }
}
</script>

<style lang="scss" scoped>
.maria-label-input{
    display: flex;
    justify-content: center;
    height: 20px;
    margin: auto;

    .labels{
        width: 80px;
        height: 25px;
        white-space: nowrap;
        padding-left: 4px;
        padding-right: 4px;
        color: white;
        background-color: #52a703;
        border-top-left-radius: 5px;
        border-bottom-left-radius: 5px;
        font-weight: 600;
    }

    input {
        color: white;
        height:15px;
        font-size: 12px;
        padding: 3px 3px;
        background-color: transparent;
        font-weight: 600;
    }
}
</style>