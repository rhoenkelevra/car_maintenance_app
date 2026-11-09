<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, errorMessage } from '../api'
import BaselineDialog from '../components/BaselineDialog.vue'
import NotificationRow from '../components/NotificationRow.vue'
import OdometerDialog from '../components/OdometerDialog.vue'
import SkipDialog from '../components/SkipDialog.vue'
import SnoozeDialog from '../components/SnoozeDialog.vue'
import { daysBetween, fmtDate, fmtKm, plural } from '../format'
import { car, dashboard, loadDashboard } from '../state'
import type { Item, Schedule, ScheduleStatus } from '../types'

const items = ref<Item[]>([])
const loading = ref(true)
const error = ref('')

const showOdometer = ref(false)
const snoozing = ref<ScheduleStatus | null>(null)
const skipping = ref<ScheduleStatus | null>(null)
const baselining = ref<ScheduleStatus | null>(null)
const busyRow = ref('')
const rowErrors = ref<Record<string, string>>({})

// Schedule definitions by id: the dashboard rows only carry the computed status.
const schedules = computed(() => {
  const map = new Map<string, Schedule>()
  for (const item of items.value) for (const s of item.schedules) map.set(s.id, s)
  return map
})

const staleDays = computed(() =>
  dashboard.value ? daysBetween(dashboard.value.last_reading_date, dashboard.value.today) : 0,
)

async function load() {
  error.value = ''
  try {
    const [, list] = await Promise.all([loadDashboard(), api.listItems()])
    items.value = list
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

function done() {
  showOdometer.value = false
  snoozing.value = skipping.value = baselining.value = null
  void load()
}

async function startToday(row: ScheduleStatus) {
  busyRow.value = row.schedule_id
  delete rowErrors.value[row.schedule_id]
  try {
    await api.setBaseline(row.item_id, row.schedule_id, { today: true })
    await load()
  } catch (e) {
    rowErrors.value[row.schedule_id] = errorMessage(e)
  } finally {
    busyRow.value = ''
  }
}

onMounted(load)
</script>

<template>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="loading && !dashboard" class="muted">Carregando…</p>

  <template v-if="dashboard">
    <header class="summary">
      <p v-if="car" class="car-name">{{ car.maker }} {{ car.model }}</p>
      <p class="km num">{{ fmtKm(dashboard.current_km) }}</p>
      <p class="muted small">Última leitura em {{ fmtDate(dashboard.last_reading_date) }}</p>
    </header>

    <div v-if="dashboard.stale" class="banner" role="status">
      <div>
        <strong>Última leitura há {{ staleDays }} {{ plural(staleDays, 'dia', 'dias') }}</strong>
        <p v-if="dashboard.estimated_km !== null" class="small">
          estimativa: ~{{ fmtKm(dashboard.estimated_km) }}
        </p>
      </div>
      <button type="button" class="btn btn-small" @click="showOdometer = true">Atualizar km</button>
    </div>

    <div class="quick">
      <RouterLink class="btn btn-primary" to="/abastecimentos/novo">+ Abastecimento</RouterLink>
      <RouterLink class="btn btn-primary" to="/manutencoes/nova">+ Manutenção</RouterLink>
      <button type="button" class="btn" @click="showOdometer = true">Atualizar km</button>
    </div>

    <h2 class="section-title">
      Pendências
      <span v-if="dashboard.notifications.length" class="muted">
        ({{ dashboard.notifications.length }})
      </span>
    </h2>
    <ul v-if="dashboard.notifications.length" class="list">
      <NotificationRow
        v-for="row in dashboard.notifications"
        :key="row.schedule_id"
        :status="row"
        :schedule="schedules.get(row.schedule_id)"
        :today="dashboard.today"
        :busy="busyRow === row.schedule_id"
        :error="rowErrors[row.schedule_id]"
        @snooze="snoozing = row"
        @skip="skipping = row"
        @baseline="baselining = row"
        @start-today="startToday(row)"
      />
    </ul>
    <div v-else class="empty">
      <strong>Tudo em dia</strong>
      Nenhuma manutenção pendente por enquanto.
    </div>

    <OdometerDialog
      v-if="showOdometer"
      :dashboard="dashboard"
      @close="showOdometer = false"
      @done="done"
    />
    <SnoozeDialog
      v-if="snoozing"
      :status="snoozing"
      :current-km="dashboard.current_km"
      @close="snoozing = null"
      @done="done"
    />
    <SkipDialog v-if="skipping" :status="skipping" @close="skipping = null" @done="done" />
    <BaselineDialog
      v-if="baselining"
      :status="baselining"
      :schedule="schedules.get(baselining.schedule_id)"
      :today="dashboard.today"
      :current-km="dashboard.current_km"
      @close="baselining = null"
      @done="done"
    />
  </template>
</template>

<style scoped>
.summary {
  margin-bottom: 16px;
}

.car-name {
  font-weight: 600;
  color: var(--muted);
}

.km {
  font-size: 2.25rem;
  font-weight: 700;
  line-height: 1.15;
}

.banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px 14px;
  border-left: 6px solid var(--upcoming-bar);
  border-radius: var(--radius);
  background: var(--upcoming-bg);
  color: var(--upcoming-ink);
}

.banner .btn {
  flex: none;
}

.quick {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.quick .btn {
  min-height: 52px;
}

.quick .btn:last-child {
  grid-column: 1 / -1;
}

@media (min-width: 768px) {
  .quick {
    grid-template-columns: repeat(3, 1fr);
  }

  .quick .btn:last-child {
    grid-column: auto;
  }
}
</style>
