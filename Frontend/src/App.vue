<template>
  <v-app>
    <v-main>
      <theMap />
    </v-main>
  </v-app>
</template>

<script lang="ts" setup>
  import theMap from '@/components/map.vue'
  import { onMounted } from 'vue'

/* ---------------- MQTT PART ---------------- */
import mqtt from 'mqtt'

let client: any

onMounted(() => {
  client = mqtt.connect('ws://localhost:9001/')

  client.on('connect', () => {
    console.log('Connected to MQTT broker')

    client.subscribe('vts/collisions/route/+/severity/+/filter/+', (err: any) => {
      if (!err) {
        console.log('Subscribed to collisions')
      }
      
    })
  })

  client.on("message", (topic: string, message: Buffer) => {
    
    try { 
      console.log('MQTT message received:')
      console.log('Topic:', topic)
      console.log('Payload:', message.toString())  
    
    }

    catch(e) {
      console.error("Failed to parse MQTT package")
    }
    
  })
})
</script>
