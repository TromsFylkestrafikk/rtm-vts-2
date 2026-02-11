<template>
  <mgl-map
    map-style="/rtm-dark.json"
    style="width: 100vw; height: 100vh"
  >

    <!-- ================= BUS ROUTES ================= -->
    <mgl-geo-json-source
      source-id="bus-routes-source"
      :data="busRoutes"
    >
      <mgl-line-layer
        layer-id="bus-routes-layer"
        :paint="busRoutePaint"
      />
    </mgl-geo-json-source>

    <!-- ================= INCIDENTS ================= -->
    <mgl-geo-json-source
      source-id="incidents-source"
      :data="incidents"
    >
      <mgl-circle-layer
        layer-id="incidents-points-layer"
        :paint="incidentCirclePaint"
        :filter="['==', '$type', 'Point']"
      />

      <mgl-line-layer
        layer-id="incidents-lines-layer"
        :paint="incidentLinePaint"
        :filter="['==', '$type', 'LineString']"
      />
    </mgl-geo-json-source>

    <!-- ================= COLLISIONS ================= -->
    <mgl-geo-json-source
      source-id="stored-collisions-source"
      :data="collisions"
    >
      <mgl-circle-layer
        layer-id="stored-collisions-layer"
        :paint="collisionPaint"
      />
    </mgl-geo-json-source>

    <!-- ================= LIVE BUS POSITIONS ================= -->
    <mgl-geo-json-source
      source-id="live-bus-source"
      :data="liveBuses"
    >
      <mgl-circle-layer
        layer-id="live-bus-layer"
        :paint="liveBusPaint"
      />
    </mgl-geo-json-source>

  </mgl-map>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  MglMap,
  MglGeoJsonSource,
  MglLineLayer,
  MglCircleLayer,
} from '@indoorequal/vue-maplibre-gl'

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

const busRoutePaint = {
  'line-color': '#00ffff',
  'line-width': 3,
}

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

const liveBusPaint = {
  'circle-radius': 5,
  'circle-color': '#00ff00',
  'circle-stroke-color': '#000000',
  'circle-stroke-width': 1,
}

/* ================= DATA FETCH ================= */

onMounted(async () => {
  busRoutes.value = await fetchJSON('/api/busroute/')
  incidents.value = await fetchJSON('/api/location_geojson/')
  collisions.value = await fetchJSON('/api/stored_collisions/')
  liveBuses.value = await fetchJSON('/api/serve_bus/')
})

async function fetchJSON(path: string) {
  const res = await fetch(`http://127.0.0.1:8000${path}`)
  return res.ok ? res.json() : emptyFC()
}


/* ---------------- MQTT PART ---------------- */

import mqtt from 'mqtt'
import { onMounted } from 'vue'

let client: any

onMounted(() => {
  client = mqtt.connect('ws://localhost:9001')

  client.on('connect', () => {
    console.log('Connected to MQTT broker')

    client.subscribe('vts/collisions/#', (err: any) => {
      if (!err) {
        console.log('Subscribed to collisions')
      }
    })
  })

  client.on('message', (topic: string, message: Buffer) => {
    console.log('MQTT message received:')
    console.log('Topic:', topic)
    console.log('Payload:', message.toString())
  })
})


</script>

<style>
@import "maplibre-gl/dist/maplibre-gl.css";
</style>
