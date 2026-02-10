<template>
  <mgl-map
    map-style="/rtm-dark.json"
    style="width: 100vw; height: 100vh"
  >
    <!-- BUS ROUTES SOURCE -->
    <mgl-geo-json-source
      source-id="bus-routes"
      :data="busRoutes"
    >
      <!-- BUS ROUTES LAYER -->
      <mgl-line-layer
        layer-id="bus-routes-layer"
        :paint="{
          'line-color': '#00ffff',
          'line-width': 3
        }"
      />
    </mgl-geo-json-source>
  </mgl-map>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  MglMap,
  MglGeoJsonSource,
  MglLineLayer,
} from '@indoorequal/vue-maplibre-gl'

const busRoutes = ref(null)

onMounted(async () => {
  const res = await fetch('http://127.0.0.1:8000/api/busroute/')
  busRoutes.value = await res.json()
})
</script>

<style>
@import "maplibre-gl/dist/maplibre-gl.css";
</style>
