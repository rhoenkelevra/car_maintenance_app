<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { api, errorMessage } from '../api'
import StatusChip from '../components/StatusChip.vue'
import { describeSchedule, triggerReason } from '../describe'
import { dashboard, loadDashboard } from '../state'
import type { Item, ScheduleStatus } from '../types'

const items = ref<Item[]>([])
const showArchived = ref(false)
const loading = ref(true)
const error = ref('')
const rowErrors = ref<Record<string, string>>({})

// Statuses come computed from the server; match them to schedules by id.
const statuses = computed(() => {
  const map = new Map<string, ScheduleStatus>()
  for (const s of dashboard.value?.statuses ?? []) map.set(s.schedule_id, s)
  return map
})

function reason(status: ScheduleStatus): string {
  const driving = status.triggers.find((t) => t.kind === status.driving)
  return driving ? triggerReason(driving) : ''
}

async function load() {
  try {
    const [list] = await Promise.all([api.listItems(showArchived.value), loadDashboard()])
    items.value = list.sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'))
    error.value = ''
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

async function restore(item: Item) {
  delete rowErrors.value[item.id]
  try {
    await api.restoreItem(item.id)
    await load()
  } catch (e) {
    rowErrors.value[item.id] = errorMessage(e)
  }
}

watch(showArchived, load)
onMounted(load)
</script>

<template>
  <div class="page-head">
    <h1>Itens</h1>
    <RouterLink class="btn btn-primary" to="/itens/novo">+ Novo item</RouterLink>
  </div>

  <label class="check">
    <input v-model="showArchived" type="checkbox" />
    <span>Mostrar arquivados</span>
  </label>

  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-else-if="loading" class="muted">Carregando…</p>
  <div v-else-if="!items.length" class="empty">
    <strong>Nenhum item</strong>
    Crie o primeiro item para acompanhar uma manutenção.
  </div>
  <ul v-else class="list">
    <li v-for="item in items" :key="item.id" :class="{ archived: item.archived }">
      <RouterLink class="list-link" :to="`/itens/${item.id}`">
        <div class="line">
          <strong>{{ item.name }}</strong>
          <span v-if="item.archived" class="badge">Arquivado</span>
        </div>
        <p v-if="item.jp_term" class="jp" lang="ja">{{ item.jp_term }}</p>

        <p v-if="!item.schedules.length" class="small muted schedule">Sem agenda</p>
        <div v-for="s in item.schedules" :key="s.id" class="schedule">
          <span class="small description">{{ describeSchedule(s) }}</span>
          <span v-if="statuses.get(s.id)" class="status">
            <span v-if="reason(statuses.get(s.id)!)" class="small muted">
              {{ reason(statuses.get(s.id)!) }}
            </span>
            <StatusChip :status="statuses.get(s.id)!.status" />
          </span>
        </div>
      </RouterLink>
      <div v-if="item.archived" class="restore">
        <button type="button" class="btn btn-small" @click="restore(item)">Restaurar</button>
        <p v-if="rowErrors[item.id]" class="error" role="alert">{{ rowErrors[item.id] }}</p>
      </div>
    </li>
  </ul>
</template>

<style scoped>
.schedule {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 4px 12px;
  margin-top: 6px;
}

.description::first-letter {
  text-transform: uppercase;
}

.status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.archived .list-link {
  opacity: 0.75;
}

.restore {
  display: grid;
  gap: 8px;
  justify-items: start;
  padding: 0 14px 12px;
}
</style>
