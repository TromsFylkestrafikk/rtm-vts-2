/**
 * plugins/index.ts
 *
 * Automatically included in `./src/main.ts`
 */

// Plugins
import vuetify from './vuetify'
import pinia from '../stores'
import router from '../router'

import 'maplibre-gl/dist/maplibre-gl.css';
import VueMaplibreGl from '@indoorequal/vue-maplibre-gl'



// Types
import type { App } from 'vue'

export function registerPlugins (app: App) {
  app
    .use(vuetify)
    .use(router)
    .use(pinia)
    .use(VueMaplibreGl)
}
