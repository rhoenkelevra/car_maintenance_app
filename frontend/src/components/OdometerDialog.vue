<script setup lang="ts">
import { ref } from 'vue'
import { api, errorMessage } from '../api'
import { fmtKm } from '../format'
import type { Dashboard } from '../types'
import AppDialog from './AppDialog.vue'
import NumField from './NumField.vue'

const props = defineProps<{ dashboard: Dashboard }>()
const emit = defineEmits<{ close: []; done: [] }>()

const date = ref(props.dashboard.today)
const km = ref<number | null>(null)
const busy = ref(false)
const error = ref('')

async function submit() {
  if (km.value === null) return
  busy.value = true
  error.value = ''
  try {
    await api.createOdometer({ date: date.value, km: km.value, note: '' })
    emit('done')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AppDialog title="Atualizar km" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <label class="field">
        <span>Km do hodômetro</span>
        <NumField v-model="km" required autofocus />
        <span class="hint">
          Último registrado: {{ fmtKm(dashboard.current_km) }}
          <template v-if="dashboard.stale && dashboard.estimated_km !== null">
            · estimativa: ~{{ fmtKm(dashboard.estimated_km) }}
          </template>
        </span>
      </label>
      <label class="field">
        <span>Data</span>
        <input v-model="date" type="date" required :max="dashboard.today" />
      </label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="dialog-actions">
        <button type="button" class="btn" @click="emit('close')">Cancelar</button>
        <button type="submit" class="btn btn-primary" :disabled="busy">Salvar</button>
      </div>
    </form>
  </AppDialog>
</template>
