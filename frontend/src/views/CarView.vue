<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorMessage } from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import NumField from '../components/NumField.vue'
import { fmtDate, fmtKm } from '../format'
import { car, dashboard, ensureCar, loadDashboard, setCar, showFlash } from '../state'
import type { Car, OdometerReading } from '../types'

const router = useRouter()

const form = reactive({
  maker: '',
  model: '',
  model_code: '',
  year: null as number | null,
  plate: '',
  tank_l: null as number | null,
  start_km: null as number | null,
  start_date: '',
  shaken_expiry: '',
  notes: '',
})

const loading = ref(true)
const loadError = ref('')
const error = ref('')
const busy = ref(false)
const exporting = ref(false)
const exportError = ref('')

// Readings made with "Atualizar km". A wrong one is deleted here and typed again.
const readings = ref<OdometerReading[]>([])
const removing = ref<OdometerReading | null>(null)
const removeBusy = ref(false)
const removeError = ref('')

/** The browser's date as YYYY-MM-DD: the server has no "today" before a car exists. */
function localToday(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

async function loadReadings() {
  const list = await api.listOdometer()
  readings.value = list.sort((a, b) => b.date.localeCompare(a.date) || b.km - a.km)
}

async function removeReading() {
  if (!removing.value) return
  removeBusy.value = true
  removeError.value = ''
  try {
    await api.deleteOdometer(removing.value.id)
    removing.value = null
    showFlash('Leitura excluída.')
    await loadReadings()
  } catch (e) {
    removeError.value = errorMessage(e)
  } finally {
    removeBusy.value = false
  }
}

onMounted(async () => {
  try {
    const current = await ensureCar()
    if (current) {
      Object.assign(form, { ...current, shaken_expiry: current.shaken_expiry ?? '' })
      // Only for today's date in the export file name.
      loadDashboard().catch(() => undefined)
      await loadReadings()
    } else {
      form.start_date = localToday()
    }
  } catch (e) {
    loadError.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})

async function submit() {
  if (form.start_km === null) return
  const first = car.value === null
  const body: Car = {
    ...form,
    maker: form.maker.trim(),
    model: form.model.trim(),
    model_code: form.model_code.trim(),
    plate: form.plate.trim(),
    start_km: form.start_km,
    shaken_expiry: form.shaken_expiry || null,
    notes: form.notes.trim(),
  }
  busy.value = true
  error.value = ''
  try {
    setCar(await api.putCar(body))
    showFlash('Carro salvo.')
    if (first) await router.replace('/')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}

async function exportAll() {
  exporting.value = true
  exportError.value = ''
  try {
    const text = await api.getExportText()
    const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `manutencao-carro-${dashboard.value?.today ?? 'export'}.json`
    document.body.append(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) {
    exportError.value = errorMessage(e)
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div class="page-head">
    <h1>Carro</h1>
  </div>

  <p v-if="loadError" class="error" role="alert">{{ loadError }}</p>
  <p v-else-if="loading" class="muted">Carregando…</p>
  <template v-else>
    <p v-if="!car" class="notice">
      <strong>Cadastre o carro para começar.</strong>
      As outras telas abrem depois disso.
    </p>

    <form class="form" @submit.prevent="submit">
      <div class="field-row">
        <label class="field">
          <span>Marca</span>
          <input v-model="form.maker" type="text" required placeholder="Toyota" />
        </label>
        <label class="field">
          <span>Modelo</span>
          <input v-model="form.model" type="text" required placeholder="Prius" />
        </label>
      </div>
      <div class="field-row">
        <label class="field">
          <span>Código do modelo</span>
          <input v-model="form.model_code" type="text" placeholder="ZVW30" />
        </label>
        <label class="field">
          <span>Ano</span>
          <NumField v-model="form.year" maxlength="4" />
        </label>
      </div>
      <div class="field-row">
        <label class="field">
          <span>Placa</span>
          <input v-model="form.plate" type="text" />
        </label>
        <label class="field">
          <span>Tanque (L)</span>
          <NumField v-model="form.tank_l" decimal />
        </label>
      </div>
      <div class="field-row">
        <label class="field">
          <span>Km inicial</span>
          <NumField v-model="form.start_km" required />
        </label>
        <label class="field">
          <span>Data inicial</span>
          <input v-model="form.start_date" type="date" required />
        </label>
      </div>
      <p class="hint">Km e data em que você começou a acompanhar o carro.</p>
      <label class="field">
        <span>Vencimento do shaken (車検)</span>
        <input v-model="form.shaken_expiry" type="date" />
        <span class="hint">Só informativo. O aviso vem da agenda do item “Vistoria (shaken)”.</span>
      </label>
      <label class="field">
        <span>Observações</span>
        <textarea v-model="form.notes" rows="2"></textarea>
      </label>

      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <button type="submit" class="btn btn-primary btn-block" :disabled="busy">
        {{ car ? 'Salvar' : 'Cadastrar carro' }}
      </button>
    </form>

    <template v-if="car">
      <h2 class="section-title">Leituras de km</h2>
      <p v-if="!readings.length" class="muted small">
        Nenhuma leitura avulsa. Elas aparecem aqui quando você usa “Atualizar km”.
      </p>
      <ul v-else class="list">
        <li v-for="reading in readings" :key="reading.id" class="reading">
          <div>
            <strong class="num">{{ fmtKm(reading.km) }}</strong>
            <div class="small muted">
              {{ fmtDate(reading.date) }}<template v-if="reading.note"> · {{ reading.note }}</template>
            </div>
          </div>
          <button
            type="button"
            class="btn btn-small"
            @click="((removing = reading), (removeError = ''))"
          >
            Excluir
          </button>
        </li>
      </ul>

      <h2 class="section-title">Dados</h2>
      <div class="stack">
        <p class="muted small">
          Baixa um arquivo com tudo: carro, itens, abastecimentos, leituras de km e manutenções.
        </p>
        <button type="button" class="btn btn-block" :disabled="exporting" @click="exportAll">
          Exportar tudo (JSON)
        </button>
        <p v-if="exportError" class="error" role="alert">{{ exportError }}</p>
      </div>
    </template>
  </template>

  <ConfirmDialog
    v-if="removing"
    title="Excluir leitura"
    :message="`Excluir a leitura de ${fmtKm(removing.km)} em ${fmtDate(removing.date)}? Os avisos são recalculados.`"
    confirm-label="Excluir"
    :busy="removeBusy"
    :error="removeError"
    @close="removing = null"
    @confirm="removeReading"
  />
</template>

<style scoped>
.reading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
}

.notice {
  margin-bottom: 16px;
  padding: 12px 14px;
  border-left: 6px solid var(--accent);
  border-radius: var(--radius);
  background: var(--surface);
}

.notice strong {
  display: block;
}
</style>
