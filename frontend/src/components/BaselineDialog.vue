<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, errorMessage } from '../api'
import { fmtKm } from '../format'
import { baselineNeeds } from '../scheduleForm'
import type { BaselineIn, Schedule, ScheduleStatus } from '../types'
import AppDialog from './AppDialog.vue'
import NumField from './NumField.vue'

const props = defineProps<{
  status: ScheduleStatus
  /** Without the definition both fields are asked. */
  schedule?: Schedule
  today: string
  currentKm: number
}>()
const emit = defineEmits<{ close: []; done: [] }>()

// Km for a km interval; date for a month or fill-up interval.
const needs = computed(() =>
  props.schedule ? baselineNeeds(props.schedule) : { km: true, date: true },
)

const km = ref<number | null>(null)
const date = ref('')
const busy = ref(false)
const error = ref('')

async function submit() {
  const body: BaselineIn = {}
  if (needs.value.km) body.km = km.value
  if (needs.value.date) body.date = date.value || null
  busy.value = true
  error.value = ''
  try {
    await api.setBaseline(props.status.item_id, props.status.schedule_id, body)
    emit('done')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AppDialog :title="`Última vez: ${status.item_name}`" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <p class="muted small">Quando isso foi feito pela última vez? A contagem parte daí.</p>
      <label v-if="needs.km" class="field">
        <span>Km da última vez</span>
        <NumField v-model="km" required autofocus />
        <span class="hint">Km atual: {{ fmtKm(currentKm) }}</span>
      </label>
      <label v-if="needs.date" class="field">
        <span>Data da última vez</span>
        <input v-model="date" type="date" required :max="today" />
      </label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="dialog-actions">
        <button type="button" class="btn" @click="emit('close')">Cancelar</button>
        <button type="submit" class="btn btn-primary" :disabled="busy">Salvar</button>
      </div>
    </form>
  </AppDialog>
</template>
