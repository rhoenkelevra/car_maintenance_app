<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, errorMessage } from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import NumField from '../components/NumField.vue'
import { normalize } from '../format'
import { goBack } from '../router'
import { dashboard, loadDashboard } from '../state'
import type { Item, MaintenanceIn } from '../types'

const props = defineProps<{ id?: string }>()
const route = useRoute()

const form = reactive({
  date: '',
  km: null as number | null,
  item_ids: [] as string[],
  cost_total: null as number | null,
  shop: '',
  notes: '',
})

const items = ref<Item[]>([])
const filter = ref('')
const loading = ref(true)
const loadError = ref('')
const error = ref('')
const busy = ref(false)
const confirmingDelete = ref(false)
const deleteError = ref('')

const adding = ref(false)
const newName = ref('')
const newJpTerm = ref('')
const newBusy = ref(false)
const newError = ref('')

// Archived items only show up while they are part of the record being edited.
const visibleItems = computed(() => {
  const needle = normalize(filter.value.trim())
  return items.value
    .filter((i) => !i.archived || form.item_ids.includes(i.id))
    .filter((i) => !needle || normalize(`${i.name} ${i.jp_term}`).includes(needle))
})

// Items already marked when the form opens go first, so they are in sight.
let pinned = new Set<string>()

function sortItems(list: Item[]): Item[] {
  return list.sort(
    (a, b) =>
      Number(pinned.has(b.id)) - Number(pinned.has(a.id)) || a.name.localeCompare(b.name, 'pt-BR'),
  )
}

onMounted(async () => {
  try {
    const [dash, list] = await Promise.all([loadDashboard(), api.listItems(!!props.id)])
    if (props.id) {
      const record = (await api.listMaintenance()).find((m) => m.id === props.id)
      if (!record) {
        loadError.value = 'Manutenção não encontrada.'
        return
      }
      Object.assign(form, {
        date: record.date,
        km: record.km,
        item_ids: [...record.item_ids],
        cost_total: record.cost_total,
        shop: record.shop,
        notes: record.notes,
      })
    } else {
      form.date = dash.today
      form.km = dash.current_km
      const preselected = route.query.item
      if (typeof preselected === 'string' && list.some((i) => i.id === preselected)) {
        form.item_ids = [preselected]
      }
    }
    pinned = new Set(form.item_ids)
    items.value = sortItems(list)
  } catch (e) {
    loadError.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})

async function addItem() {
  const name = newName.value.trim()
  if (!name) {
    newError.value = 'Informe o nome do item.'
    return
  }
  newBusy.value = true
  newError.value = ''
  try {
    const item = await api.createItem({
      name,
      jp_term: newJpTerm.value.trim(),
      notes: '',
      schedules: [],
    })
    items.value = sortItems([...items.value, item])
    form.item_ids.push(item.id)
    filter.value = ''
    newName.value = newJpTerm.value = ''
    adding.value = false
  } catch (e) {
    newError.value = errorMessage(e)
  } finally {
    newBusy.value = false
  }
}

async function submit() {
  if (form.km === null) return
  if (!form.item_ids.length) {
    error.value = 'Marque ao menos um item.'
    return
  }
  const body: MaintenanceIn = {
    ...form,
    km: form.km,
    shop: form.shop.trim(),
    notes: form.notes.trim(),
  }
  busy.value = true
  error.value = ''
  try {
    if (props.id) await api.updateMaintenance(props.id, body)
    else await api.createMaintenance(body)
    goBack('/manutencoes')
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
    await api.deleteMaintenance(props.id)
    goBack('/manutencoes')
  } catch (e) {
    deleteError.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page-head">
    <h1>{{ id ? 'Editar manutenção' : 'Nova manutenção' }}</h1>
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

    <fieldset class="field">
      <legend class="legend">
        Itens feitos
        <span class="muted">({{ form.item_ids.length }} marcado{{ form.item_ids.length === 1 ? '' : 's' }})</span>
      </legend>
      <input
        v-model="filter"
        type="search"
        placeholder="Filtrar itens"
        aria-label="Filtrar itens"
        @keydown.enter.prevent
      />
      <div class="items">
        <label v-for="item in visibleItems" :key="item.id" class="check item">
          <input v-model="form.item_ids" type="checkbox" :value="item.id" />
          <span class="item-text">
            <span>
              {{ item.name }}
              <span v-if="item.archived" class="muted">(arquivado)</span>
            </span>
            <span v-if="item.jp_term" class="jp" lang="ja">{{ item.jp_term }}</span>
          </span>
        </label>
        <p v-if="!visibleItems.length" class="muted small none">
          {{ filter.trim() ? 'Nenhum item com esse filtro.' : 'Nenhum item ainda. Crie um abaixo.' }}
        </p>
      </div>

      <button v-if="!adding" type="button" class="btn btn-small" @click="adding = true">
        + Novo item
      </button>
      <div v-else class="card new-item">
        <p class="hint">Para um serviço sem agenda. Dá para criar a agenda depois, em Itens.</p>
        <label class="field">
          <span>Nome</span>
          <input v-model="newName" type="text" @keydown.enter.prevent="addItem" />
        </label>
        <label class="field">
          <span>Termo em japonês (opcional)</span>
          <input v-model="newJpTerm" type="text" lang="ja" @keydown.enter.prevent="addItem" />
        </label>
        <p v-if="newError" class="error" role="alert">{{ newError }}</p>
        <div class="dialog-actions">
          <button type="button" class="btn btn-small" @click="adding = false">Cancelar</button>
          <button type="button" class="btn btn-small btn-primary" :disabled="newBusy" @click="addItem">
            Adicionar item
          </button>
        </div>
      </div>
    </fieldset>

    <div class="field-row">
      <label class="field">
        <span>Custo total (¥)</span>
        <NumField v-model="form.cost_total" />
      </label>
      <label class="field">
        <span>Oficina / loja</span>
        <input v-model="form.shop" type="text" />
      </label>
    </div>

    <label class="field">
      <span>Observações</span>
      <textarea v-model="form.notes" rows="2"></textarea>
    </label>

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <div class="form-actions">
      <button type="button" class="btn" @click="goBack('/manutencoes')">Cancelar</button>
      <button type="submit" class="btn btn-primary" :disabled="busy">Salvar</button>
    </div>
    <button v-if="id" type="button" class="btn btn-danger" @click="confirmingDelete = true">
      Excluir manutenção
    </button>
  </form>

  <ConfirmDialog
    v-if="confirmingDelete"
    title="Excluir manutenção?"
    message="O registro some do histórico e os avisos são recalculados sem ele."
    confirm-label="Excluir"
    :busy="busy"
    :error="deleteError"
    @close="confirmingDelete = false"
    @confirm="remove"
  />
</template>

<style scoped>
fieldset.field {
  gap: 8px;
}

.legend {
  margin-bottom: 4px;
}

.items {
  max-height: 44vh;
  overflow-y: auto;
  overscroll-behavior: contain;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
}

.item {
  padding: 6px 12px;
  min-height: 48px;
}

.item + .item {
  border-top: 1px solid var(--border);
}

.item-text {
  display: grid;
  min-width: 0;
}

.none {
  padding: 12px;
}

.new-item {
  display: grid;
  gap: 12px;
}
</style>
