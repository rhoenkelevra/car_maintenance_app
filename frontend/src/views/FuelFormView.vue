<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api, errorMessage } from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import NumField from '../components/NumField.vue'
import { fmtKm } from '../format'
import { goBack } from '../router'
import { dashboard, loadDashboard } from '../state'
import type { FuelLogIn } from '../types'

const props = defineProps<{ id?: string }>()

const FUEL_TYPES = [
  { value: 'regular', label: 'Regular (レギュラー)' },
  { value: 'premium', label: 'Premium (ハイオク)' },
  { value: 'diesel', label: 'Diesel (軽油)' },
]

const form = reactive({
  date: '',
  km: null as number | null,
  litres: null as number | null,
  price_total: null as number | null,
  full_tank: true,
  fuel_type: 'regular',
  station: '',
  notes: '',
})

const loading = ref(true)
const loadError = ref('')
const error = ref('')
const busy = ref(false)
const confirmingDelete = ref(false)
const deleteError = ref('')

// Keep a stored fuel type that is not one of the usual three selectable.
const fuelTypes = computed(() =>
  FUEL_TYPES.some((t) => t.value === form.fuel_type)
    ? FUEL_TYPES
    : [...FUEL_TYPES, { value: form.fuel_type, label: form.fuel_type }],
)

onMounted(async () => {
  try {
    const today = (await loadDashboard()).today
    if (props.id) {
      const log = (await api.listFuel()).find((f) => f.id === props.id)
      if (!log) {
        loadError.value = 'Abastecimento não encontrado.'
        return
      }
      const { id: _id, ...fields } = log
      Object.assign(form, fields)
    } else {
      form.date = today
    }
  } catch (e) {
    loadError.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})

async function submit() {
  if (form.km === null) return
  const body: FuelLogIn = {
    ...form,
    km: form.km,
    station: form.station.trim(),
    notes: form.notes.trim(),
  }
  busy.value = true
  error.value = ''
  try {
    if (props.id) await api.updateFuel(props.id, body)
    else await api.createFuel(body)
    goBack('/abastecimentos')
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
    await api.deleteFuel(props.id)
    goBack('/abastecimentos')
  } catch (e) {
    deleteError.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page-head">
    <h1>{{ id ? 'Editar abastecimento' : 'Novo abastecimento' }}</h1>
  </div>

  <p v-if="loadError" class="error" role="alert">{{ loadError }}</p>
  <p v-else-if="loading" class="muted">Carregando…</p>
  <form v-else class="form" @submit.prevent="submit">
    <div class="field-row">
      <label class="field">
        <span>Data</span>
        <input v-model="form.date" type="date" required :max="dashboard?.today" />
      </label>
      <label class="field">
        <span>Km do hodômetro</span>
        <NumField v-model="form.km" required />
      </label>
    </div>
    <p v-if="dashboard && !id" class="hint">Último km registrado: {{ fmtKm(dashboard.current_km) }}</p>

    <div class="field-row">
      <label class="field">
        <span>Litros</span>
        <NumField v-model="form.litres" decimal placeholder="0,0" />
      </label>
      <label class="field">
        <span>Total pago (¥)</span>
        <NumField v-model="form.price_total" />
      </label>
    </div>

    <label class="check">
      <input v-model="form.full_tank" type="checkbox" />
      <span>Tanque cheio</span>
    </label>

    <label class="field">
      <span>Combustível</span>
      <select v-model="form.fuel_type">
        <option v-for="t in fuelTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
      </select>
    </label>

    <label class="field">
      <span>Posto</span>
      <input v-model="form.station" type="text" />
    </label>

    <label class="field">
      <span>Observações</span>
      <textarea v-model="form.notes" rows="2"></textarea>
    </label>

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <div class="form-actions">
      <button type="button" class="btn" @click="goBack('/abastecimentos')">Cancelar</button>
      <button type="submit" class="btn btn-primary" :disabled="busy">Salvar</button>
    </div>
    <button v-if="id" type="button" class="btn btn-danger" @click="confirmingDelete = true">
      Excluir abastecimento
    </button>
  </form>

  <ConfirmDialog
    v-if="confirmingDelete"
    title="Excluir abastecimento?"
    message="O registro some e os avisos são recalculados sem ele."
    confirm-label="Excluir"
    :busy="busy"
    :error="deleteError"
    @close="confirmingDelete = false"
    @confirm="remove"
  />
</template>
