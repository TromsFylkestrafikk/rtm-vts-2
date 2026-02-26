<script setup lang="ts">
const props = defineProps<{ data: any }>()
const emit = defineEmits(['close'])
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="modal">

      <!-- HEADER -->
      <div class="modal-header">
        <div class="title">
          {{ props.data?.situation_type }}
        </div>

        <v-btn icon variant="text" size="small" @click="emit('close')">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </div>

      <!-- DESCRIPTION -->
      <div class="description">
        {{ props.data?.description }}
      </div>

      <div class="divider"></div>

      <!-- INFO GRID -->
      <div class="info">
        <div class="row">
          <span class="label">Vei</span>
          <span>{{ props.data?.name }}</span>
        </div>

        <div class="row">
          <span class="label">Fylke</span>
          <span>{{ props.data?.county }}</span>
        </div>

        <div class="row">
          <span class="label">Kommentar</span>
          <span>{{ props.data?.comment }}</span>
        </div>

        <div class="row">
          <span class="label">Alvorlighet</span>
          <span :class="severityClass">
            {{ props.data?.severity }}
          </span>
        </div>
      </div>

    </div>
  </div>
</template>

<script lang="ts">
export default {
  computed: {
    severityClass(): string {
      switch (this.data?.severity) {
        case 'highest': return 'severity-high'
        case 'high': return 'severity-medium'
        case 'low': return 'severity-low'
        default: return 'severity-unknown'
      }
    }
  }
}
</script>

<style scoped>
/* DARK OVERLAY */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 15, 25, 0.75);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

/* MODAL CARD */
.modal {
  width: 420px;
  background: #1e1f25;
  color: #f5f5f5;
  border-radius: 18px;
  padding: 24px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.6);
  animation: fadeIn 0.2s ease;
}

/* HEADER */
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 20px;
  font-weight: 600;
}

/* DESCRIPTION */
.description {
  margin-top: 12px;
  color: #c9c9c9;
}

.divider {
  height: 1px;
  background: rgba(255,255,255,0.08);
  margin: 16px 0;
}

.info .row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.label {
  color: #888;
}

/* SEVERITY COLORS */
.severity-high {
  color: #ff4d4d;
}

.severity-medium {
  color: #ff9800;
}

.severity-low {
  color: #4caf50;
}

.severity-unknown {
  color: #999;
}

@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
</style>