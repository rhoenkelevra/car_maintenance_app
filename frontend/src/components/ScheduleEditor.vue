<script setup lang="ts">
import { MONTHS, describeSchedule } from '../describe'
import { newScheduleForm, toSchedulePayload, type ScheduleForm } from '../scheduleForm'
import NumField from './NumField.vue'

// The list is edited in place; the parent sends it whole when the item is saved.
const schedules = defineModel<ScheduleForm[]>({ required: true })

function add() {
  schedules.value.push(newScheduleForm())
}

function remove(index: number) {
  schedules.value.splice(index, 1)
}
</script>

<template>
  <div class="stack">
    <p v-if="!schedules.length" class="muted small">
      Sem agenda: o item serve só para registrar serviços avulsos.
    </p>

    <section v-for="(s, index) in schedules" :key="s.key" class="card schedule">
      <header class="line">
        <div>
          <h3>Agenda {{ index + 1 }}</h3>
          <p class="small muted summary">{{ describeSchedule(toSchedulePayload(s)) }}</p>
        </div>
        <button type="button" class="btn btn-small btn-danger" @click="remove(index)">
          Remover
        </button>
      </header>

      <label class="field">
        <span>Tipo</span>
        <select v-model="s.type">
          <option value="interval">Por intervalo</option>
          <option value="yearly">Todo ano, em meses fixos</option>
          <option value="one_time">Evento único</option>
        </select>
      </label>

      <template v-if="s.type === 'interval'">
        <fieldset class="stack">
          <legend class="legend">A cada (o que vier primeiro)</legend>
          <div class="field-row">
            <label class="field">
              <span>Km</span>
              <NumField v-model="s.every_km" />
            </label>
            <label class="field">
              <span>Meses</span>
              <NumField v-model="s.every_months" />
            </label>
          </div>
          <label v-if="s.anchor === 'actual'" class="field">
            <span>Abastecimentos</span>
            <NumField v-model="s.every_fillups" />
          </label>
        </fieldset>

        <fieldset>
          <legend class="legend">Contagem</legend>
          <label class="check">
            <input v-model="s.anchor" type="radio" :name="`anchor-${s.key}`" value="actual" />
            <span>Contar a partir da última vez feita</span>
          </label>
          <label class="check">
            <input v-model="s.anchor" type="radio" :name="`anchor-${s.key}`" value="fixed" />
            <span>Datas fixas</span>
          </label>
        </fieldset>

        <fieldset v-if="s.anchor === 'actual'" class="stack">
          <legend class="legend">Última vez (opcional)</legend>
          <div class="field-row">
            <label class="field">
              <span>Km</span>
              <NumField v-model="s.baseline_km" />
            </label>
            <label class="field">
              <span>Data</span>
              <input v-model="s.baseline_date" type="date" />
            </label>
          </div>
          <p class="hint">
            Sem isso a agenda fica “Sem histórico” até a primeira manutenção registrada.
          </p>
        </fieldset>

        <fieldset v-else class="stack">
          <legend class="legend">Primeiro vencimento</legend>
          <div class="field-row">
            <label class="field">
              <span>Km</span>
              <NumField v-model="s.first_due_km" />
            </label>
            <label class="field">
              <span>Data</span>
              <input v-model="s.first_due_date" type="date" />
            </label>
          </div>
          <p class="hint">Os vencimentos seguintes repetem o intervalo a partir daqui.</p>
        </fieldset>
      </template>

      <template v-else-if="s.type === 'yearly'">
        <fieldset>
          <legend class="legend">Meses</legend>
          <div class="months">
            <label v-for="(name, m) in MONTHS" :key="name" class="check">
              <input v-model="s.months" type="checkbox" :value="m + 1" />
              <span>{{ name.slice(0, 3) }}</span>
            </label>
          </div>
        </fieldset>
        <label class="field day">
          <span>Dia</span>
          <NumField v-model="s.day" />
        </label>
      </template>

      <template v-else>
        <div class="field-row">
          <label class="field">
            <span>Aos (km)</span>
            <NumField v-model="s.at_km" />
          </label>
          <label class="field">
            <span>Em (data)</span>
            <input v-model="s.on_date" type="date" />
          </label>
        </div>
        <p class="hint">Km, data ou os dois: vale o que vier primeiro.</p>
      </template>

      <details class="advanced">
        <summary>Avançado</summary>
        <div class="stack advanced-body">
          <p class="hint">
            Quando avisar (amarelo) e quando marcar como atrasado (vermelho). Vazio = automático
            (10% do intervalo).
          </p>
          <div class="field-row">
            <label class="field">
              <span>Avisar antes (km)</span>
              <NumField v-model="s.lead_km" placeholder="automático" />
            </label>
            <label class="field">
              <span>Avisar antes (dias)</span>
              <NumField v-model="s.lead_days" placeholder="automático" />
            </label>
          </div>
          <div class="field-row">
            <label class="field">
              <span>Atrasado após (km)</span>
              <NumField v-model="s.overdue_km" placeholder="automático" />
            </label>
            <label class="field">
              <span>Atrasado após (dias)</span>
              <NumField v-model="s.overdue_days" placeholder="automático" />
            </label>
          </div>
          <label class="check">
            <input v-model="s.active" type="checkbox" />
            <span>Agenda ativa</span>
          </label>
        </div>
      </details>
    </section>

    <button type="button" class="btn" @click="add">+ Adicionar agenda</button>
  </div>
</template>

<style scoped>
.schedule {
  display: grid;
  gap: 14px;
}

h3 {
  font-size: 1rem;
}

.summary::first-letter {
  text-transform: uppercase;
}

.legend {
  margin-bottom: 6px;
}

.months {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0 8px;
}

.day {
  max-width: 120px;
}

.advanced summary {
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  cursor: pointer;
  list-style: none;
}

.advanced summary::-webkit-details-marker {
  display: none;
}

.advanced summary::before {
  content: '▸';
}

.advanced[open] summary::before {
  content: '▾';
}

.advanced-body {
  padding-top: 4px;
}
</style>
