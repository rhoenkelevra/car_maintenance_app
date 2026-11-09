<script setup lang="ts">
import { ref } from 'vue'
import { api, errorMessage } from '../api'
import type { ScheduleStatus } from '../types'
import AppDialog from './AppDialog.vue'

const props = defineProps<{ status: ScheduleStatus }>()
const emit = defineEmits<{ close: []; done: [] }>()

const note = ref('')
const busy = ref(false)
const error = ref('')

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await api.skip(props.status.item_id, props.status.schedule_id, { note: note.value.trim() })
    emit('done')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AppDialog :title="`Pular: ${status.item_name}`" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <p>
        Pular este ciclo sem registrar manutenção? O aviso some e só volta no próximo ciclo. Dá para
        desfazer em Manutenções.
      </p>
      <label class="field">
        <span>Observação (opcional)</span>
        <input v-model="note" type="text" />
      </label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="dialog-actions">
        <button type="button" class="btn" @click="emit('close')">Cancelar</button>
        <button type="submit" class="btn btn-primary" :disabled="busy">Pular</button>
      </div>
    </form>
  </AppDialog>
</template>
