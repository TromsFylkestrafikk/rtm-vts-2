<template>

    <mgl-map map-style="/rtm-dark.json">
      
    
    <mgl-navigation-control />
    
    <trafficBtn @toggle="showIncidents = !showIncidents" />

    <mgl-geo-json-source
      source-id="bus-routes-source"
      :data="busRoutes"
    >
      <mgl-line-layer
        layer-id="bus-routes-layer"
        :paint="{
          'line-color': '#ffffff',
          'line-width': 4
        }"
      />
    </mgl-geo-json-source>


    

    <!-- ================= INCIDENTS ================= -->
    <mgl-geo-json-source
      v-if="showIncidents"
      source-id="incidents-source"
      :data="incidents"
    >

      
        <mgl-circle-layer
          layer-id="incidents-points-layer"
          :paint="incidentCirclePaint"
          :filter="['==', '$type', 'Point']"
          @click="test"
        />
      

      </mgl-geo-json-source>

      
      <mgl-geo-json-source
        source-id="stored-collisions-source"
        :data="collisions"
      >
        <mgl-circle-layer
          layer-id="stored-collisions-layer"
          :paint="collisionPaint"
        />
      </mgl-geo-json-source>


    </mgl-map>

    <msgWindow
      v-if="selectedFeature"
      :data="selectedFeature"
      @close="selectedFeature = null"
    />

</template>
  
<script setup lang="ts">
  import { ref, onMounted, computed } from 'vue'
  import mqtt from "mqtt"
  import {
    MglMap,
    MglGeoJsonSource,
    MglLineLayer,
    MglCircleLayer,
    MglNavigationControl,
  } from '@indoorequal/vue-maplibre-gl'

  const selectedFeature = ref<any>(null)
  const popupCoordinates = ref<[number, number] | null>(null)
  const showIncidents = ref(false)

  defineProps(['coordinates'])
  
  import trafficBtn from "@/components/trafficBtn.vue"
  import msgWindow from "@/components/msgWindow.vue"
  import trafficIcon from '@/pages/trafficIcon.vue'
  
 /* ================= GEOJSON STATE ================= */

const emptyFC = () => ({ type: 'FeatureCollection', features: [] })

const busRoutes  = ref(emptyFC())
const incidents  = ref(emptyFC())
const collisions = ref(emptyFC())
const liveBuses  = ref(emptyFC())

/* ================= STYLES ================= */

const severityColor = [
  'match',
  ['get', 'severity'],
  'none', '#7e4da3',
  'low', '#ffff00',
  'high', '#ffa500',
  'highest', '#ff0000',
  'unknown', '#808080',
  '#0000ff',
]

const incidentCirclePaint = {
  'circle-radius': 6,
  'circle-opacity': 0.9,
  'circle-color': severityColor,
}

const incidentLinePaint = {
  'line-width': 4,
  'line-dasharray': [2, 2],
  'line-color': severityColor,
}

const collisionPaint = {
  'circle-radius': 8,
  'circle-opacity': 0.85,
  'circle-color': severityColor,
  'circle-stroke-color': '#ffffff',
  'circle-stroke-width': 1,
}

/* ================= DATA FETCH ================= */
const client = mqtt.connect("ws://localhost:9001")

client.on("connect", () => {
  console.log("MQTT connected")

  client.subscribe("vts/collisions/#")
})

client.on("message", (topic, message) => {

  const data = JSON.parse(message.toString())

  console.log("MQTT message received:", topic, data)

  if (topic.includes("collisions")) {

    const feature = {
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [data.lon, data.lat]
      },
      properties: data
    }

    collisions.value.features.push(feature)
  }
})

onMounted(async () => {
  busRoutes.value = await fetchJSON('/api/busroute/')
  incidents.value = await fetchJSON('/api/location_geojson/')
  //collisions.value = await fetchJSON('/api/stored_collisions/')
  //liveBuses.value = await fetchJSON('/api/serve_bus/')
})

async function fetchJSON(path: string) {
  const res = await fetch(`http://127.0.0.1:8000${path}`)
  
  return res.ok ? res.json() : emptyFC() //Returns json package if the result is ok (aka. status code 200 )
}

  function test(e: any) {
    const feature = e.features?.[0]
    if (!feature) return

    selectedFeature.value = feature.properties
    popupCoordinates.value = feature.geometry.coordinates
  }

  </script>
  
  <style>
  @import "maplibre-gl/dist/maplibre-gl.css";  
  
  </style>
  