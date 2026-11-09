<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, errorMessage } from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { fmtDate, fmtKm, fmtYen } from '../format'
import type { HistoryEntry } from '../types'

const entries = ref<HistoryEntry[]>([])
const loading = ref(true)
const error = ref('')

const undoing = ref<HistoryEntry | null>(null)
const undoBusy = ref(false)
const undoError = ref('')

function snoozedUntil(entry: HistoryEntry): string {
  const parts: string[] = []
  if (entry.until_km !== null) parts.push(fmtKm(entry.until_km))
  if (entry.until_date) parts.push(fmtDate(entry.until_date))
  return parts.join(' ou ')
}

async function load() {
  try {
    entries.value = await api.getHistory()
    error.value = ''
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

async function undo() {
  if (!undoing.value) return
  undoBusy.value = true
  undoError.value = ''
  try {
    await api.deleteEvent(undoing.value.id)
    undoing.value = null
    await load()
  } catch (e) {
    undoError.value = errorMessage(e)
  } finally {
    undoBusy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-head">
    <h1>Manutenções</h1>
    <RouterLink class="btn btn-primary" to="/manutencoes/nova">+ Manutenção</RouterLink>
  </div>

  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-else-if="loading" class="muted">Carregando…</p>
  <div v-else-if="!entries.length" class="empty">
    <strong>Nenhum registro</strong>
    As manutenções feitas, puladas e adiadas aparecem aqui.
  </div>
  <ul v-else class="list">
    <li v-for="entry in entries" :key="`${entry.kind}-${entry.id}`">
      <RouterLink
        v-if="entry.kind === 'maintenance'"
        class="list-link"
        :to="`/manutencoes/${entry.id}`"
      >
        <div class="line small muted num">
          <span>{{ fmtDate(entry.date) }}</span>
          <span>{{ fmtKm(entry.km) }}</span>
        </div>
        <p class="names">{{ entry.item_names.join(', ') }}</p>
        <p v-if="entry.cost_total !== null || entry.shop" class="small muted num">
          <template v-if="entry.cost_total !== null">{{ fmtYen(entry.cost_total) }}</template>
          <template v-if="entry.cost_total !== null && entry.shop"> · </template>
          {{ entry.shop }}
        </p>
        <p v-if="entry.notes" class="small muted">{{ entry.notes }}</p>
      </RouterLink>

      <div v-else class="event">
        <div class="event-text">
          <div class="line small muted num">
            <span>{{ fmtDate(entry.date) }}</span>
            <span>{{ fmtKm(entry.km) }}</span>
          </div>
          <p class="names">{{ entry.item_names.join(', ') }}</p>
          <p>
            <span class="badge">
              {{ entry.kind === 'skip' ? 'Pulado' : `Adiado até ${snoozedUntil(entry)}` }}
            </span>
          </p>
          <p v-if="entry.notes" class="small muted">{{ entry.notes }}</p>
        </div>
        <button type="button" class="btn btn-small" @click="((undoError = ''), (undoing = entry))">
          Desfazer
        </button>
      </div>
    </li>
  </ul>

  <ConfirmDialog
    v-if="undoing"
    :title="undoing.kind === 'skip' ? 'Desfazer o pulo?' : 'Desfazer o adiamento?'"
    :message="`${undoing.item_names.join(', ')}: o aviso volta a valer como antes.`"
    confirm-label="Desfazer"
    :busy="undoBusy"
    :error="undoError"
    @close="undoing = null"
    @confirm="undo"
  />
</template>

<style scoped>
.names {
  font-weight: 600;
}

.event {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
}

.event-text {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 2px;
}

.badge {
  white-space: normal;
}
</style>
