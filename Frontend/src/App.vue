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
  client = mqtt.connect('ws://127.0.0.1:9001')

  client.on('connect', () => {
    console.log('Connected to MQTT broker')

    client.subscribe('vts/collisions/#', (err: any) => {
      if (!err) {
        console.log('Subscribed to collisions')
      }
      
    })
  })

  client.on("message", (topic: string, message: Buffer, err: any) => {
    
    if(!err) { 
      console.log('MQTT message received:')
      console.log('Topic:', topic)
      console.log('Payload:', message.toString())  
    
    }

    else if(err) {
      console.log("Could not get the messsage:",err)
    } 
  })
})
</script>
