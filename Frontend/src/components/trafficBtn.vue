<script setup lang="ts"> 
//
import {
  MglMarker, 
  MglPopup
} from '@indoorequal/vue-maplibre-gl'

import {trafficIcon} from "@/components/trafficIcon.vue"


function togglePopup() { 
    
}


</script>

<template> 

  <v-btn class = "iconBtn" color = "warning" icon="mdi-plus" size ="x-small" v-on:click ="">
    
  </v-btn>
  
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