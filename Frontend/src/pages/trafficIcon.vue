<script setup lang="ts"> 
//
import {
  MglMarker, 
  MglPopup
} from '@indoorequal/vue-maplibre-gl'

import { msgWindow} from "@/components/msgWindow.vue"

import { useTemplateRef } from 'vue'


const center = [12.550343, 55.665957];
const zoom = 8;
const coordinates = [18.91, 69.68];

const popupRef = useTemplateRef('popup') //use the template for the icon here
const closePopup = () => {
  popupRef.value.remove()
};



</script>

<template> 

<mgl-marker :coordinates="coordinates">
      <mgl-popup ref="popup">
        <a href="#" @click.prevent="closePopup">Close popup</a>
      </mgl-popup>
    </mgl-marker>s
  
</template>


Only allows to style within this component 
<style scoped> 
  .iconBtn {
    position: absolute;
    z-index: 100;   
    
  }

</style>