<script setup lang="ts">
const emit = defineEmits(['toggle'])

function toggleLayer() {
  emit('toggle')
}
</script>

<template>
  <v-btn
    class="iconBtn"
    color="warning"
    icon="mdi-alert"
    size="x-small"
    @click="toggleLayer"
  />
</template>


Only allows to style within this component 
<style scoped> 
  .iconBtn {
    position: absolute;
    z-index: 100;  
    right: 8px;
    top: 200px;
    transform: translate((-50%), (-50%));
    
  }

</style>