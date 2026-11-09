<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, errorMessage } from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import ScheduleEditor from '../components/ScheduleEditor.vue'
import { goBack } from '../router'
import { toScheduleForm, toSchedulePayload, type ScheduleForm } from '../scheduleForm'
import { showFlash } from '../state'
import type { ItemIn } from '../types'

const props = defineProps<{ id?: string }>()

const name = ref('')
const jpTerm = ref('')
const notes = ref('')
const schedules = ref<ScheduleForm[]>([])
const archived = ref(false)

const loading = ref(!!props.id)
const loadError = ref('')
const error = ref('')
const busy = ref(false)
const confirmingDelete = ref(false)
const deleteError = ref('')

onMounted(async () => {
  if (!props.id) return
  try {
    const item = await api.getItem(props.id)
    name.value = item.name
    jpTerm.value = item.jp_term
    notes.value = item.notes
    archived.value = item.archived
    schedules.value = item.schedules.map(toScheduleForm)
  } catch (e) {
    loadError.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})

async function submit() {
  // Existing schedules keep their id so the server preserves them; new ones have none.
  const body: ItemIn = {
    name: name.value.trim(),
    jp_term: jpTerm.value.trim(),
    notes: notes.value.trim(),
    schedules: schedules.value.map(toSchedulePayload),
  }
  busy.value = true
  error.value = ''
  try {
    if (props.id) await api.updateItem(props.id, body)
    else await api.createItem(body)
    goBack('/itens')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}

async function remove() {
  if (!props.id) return
  busy.value = true
  deleteError.value = ''
  try {
    const result = await api.deleteItem(props.id)
    showFlash(
      result.archived
        ? `“${name.value}” tem histórico, então foi arquivado em vez de excluído.`
        : `“${name.value}” foi excluído.`,
    )
    goBack('/itens')
  } catch (e) {
    deleteError.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page-head">
    <h1>{{ id ? 'Editar item' : 'Novo item' }}</h1>
    <span v-if="archived" class="badge">Arquivado</span>
  </div>

  <p v-if="loadError" class="error" role="alert">{{ loadError }}</p>
  <p v-else-if="loading" class="muted">Carregando…</p>
  <form v-else class="form" @submit.prevent="submit">
    <label class="field">
      <span>Nome</span>
      <input v-model="name" type="text" required />
    </label>
    <label class="field">
      <span>Termo em japonês</span>
      <input v-model="jpTerm" type="text" lang="ja" placeholder="ex.: エンジンオイル交換" />
    </label>
    <label class="field">
      <span>Observações</span>
      <textarea v-model="notes" rows="2"></textarea>
    </label>

    <h2 class="section-title">Agendas</h2>
    <ScheduleEditor v-model="schedules" />

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <div class="form-actions">
      <button type="button" class="btn" @click="goBack('/itens')">Cancelar</button>
      <button type="submit" class="btn btn-primary" :disabled="busy">Salvar</button>
    </div>
    <button
      v-if="id && !archived"
      type="button"
      class="btn btn-danger"
      @click="confirmingDelete = true"
    >
      Excluir item
    </button>
  </form>

  <ConfirmDialog
    v-if="confirmingDelete"
    title="Excluir item?"
    message="Se o item já tiver histórico, ele é arquivado em vez de excluído."
    confirm-label="Excluir"
    :busy="busy"
    :error="deleteError"
    @close="confirmingDelete = false"
    @confirm="remove"
  />
</template>

<style scoped>
.section-title {
  margin: 8px 0 0;
}
</style>
