<script setup lang="ts">
import { ref } from 'vue'
import { api, errorMessage } from '../api'
import { fmtKm } from '../format'
import type { ScheduleStatus } from '../types'
import AppDialog from './AppDialog.vue'
import NumField from './NumField.vue'

const props = defineProps<{ status: ScheduleStatus; currentKm: number }>()
const emit = defineEmits<{ close: []; done: [] }>()

const untilKm = ref<number | null>(null)
const untilDate = ref('')
const note = ref('')
const busy = ref(false)
const error = ref('')

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await api.snooze(props.status.item_id, props.status.schedule_id, {
      until_km: untilKm.value,
      until_date: untilDate.value || null,
      note: note.value.trim(),
    })
    emit('done')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AppDialog :title="`Adiar: ${status.item_name}`" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <p class="muted small">Avisar de novo quando chegar a um km, a uma data, ou ao que vier primeiro.</p>
      <label class="field">
        <span>Até o km</span>
        <NumField v-model="untilKm" autofocus />
        <span class="hint">Km atual: {{ fmtKm(currentKm) }}</span>
      </label>
      <label class="field">
        <span>Até a data</span>
        <input v-model="untilDate" type="date" />
      </label>
      <label class="field">
        <span>Observação (opcional)</span>
        <input v-model="note" type="text" />
      </label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="dialog-actions">
        <button type="button" class="btn" @click="emit('close')">Cancelar</button>
        <button type="submit" class="btn btn-primary" :disabled="busy">Adiar</button>
      </div>
    </form>
  </AppDialog>
</template>
