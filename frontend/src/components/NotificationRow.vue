<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { STATUS_LABEL, describeSchedule, projection, triggerDue, triggerReason } from '../describe'
import type { Schedule, ScheduleStatus } from '../types'

const props = defineProps<{
  status: ScheduleStatus
  /** The schedule's definition, when the item list has it. */
  schedule?: Schedule
  today: string
  busy?: boolean
  error?: string
}>()

const emit = defineEmits<{ snooze: []; skip: []; baseline: []; startToday: [] }>()

// `driving` names the kind of the trigger that set the row's colour.
const driving = computed(
  () => props.status.triggers.find((t) => t.kind === props.status.driving) ?? null,
)
const others = computed(() => props.status.triggers.filter((t) => t !== driving.value))
const hint = computed(() => (driving.value ? projection(driving.value, props.today) : ''))
</script>

<template>
  <li class="row" :class="`row-${status.status}`">
    <div class="head">
      <div class="title">
        <strong>{{ status.item_name }}</strong>
        <span v-if="status.jp_term" class="jp" lang="ja">{{ status.jp_term }}</span>
      </div>
      <div class="state">
        <span class="label">{{ STATUS_LABEL[status.status] }}</span>
        <span v-if="status.snoozed" class="badge">adiado</span>
      </div>
    </div>

    <div class="why">
      <p v-if="driving" class="reason">
        <span class="reason-text">{{ triggerReason(driving) }}</span>
        <span v-if="triggerDue(driving)" class="due"> · {{ triggerDue(driving) }}</span>
        <span v-if="hint" class="due"> · {{ hint }}</span>
      </p>
      <p v-else class="reason">Ainda não sei quando foi a última vez.</p>
      <p v-for="t in others" :key="t.kind" class="other">
        {{ triggerReason(t) }}<template v-if="triggerDue(t)"> ({{ triggerDue(t) }})</template>
      </p>
      <p v-if="schedule" class="other">Agenda: {{ describeSchedule(schedule) }}</p>
    </div>

    <div v-if="status.status === 'no_history'" class="actions">
      <button type="button" class="btn btn-small" :disabled="busy" @click="emit('baseline')">
        Informar última vez
      </button>
      <button type="button" class="btn btn-small" :disabled="busy" @click="emit('startToday')">
        Começar a contar de hoje
      </button>
    </div>
    <div v-else class="actions">
      <RouterLink
        class="btn btn-small btn-primary"
        :to="{ path: '/manutencoes/nova', query: { item: status.item_id } }"
      >
        Registrar
      </RouterLink>
      <button type="button" class="btn btn-small" @click="emit('snooze')">Adiar</button>
      <button type="button" class="btn btn-small" @click="emit('skip')">Pular</button>
    </div>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
  </li>
</template>

<style scoped>
.row {
  display: grid;
  gap: 8px;
  padding: 12px 14px 12px 12px;
  border-left: 6px solid var(--bar);
  background: var(--tint);
}

.row-upcoming {
  --tint: var(--upcoming-bg);
  --bar: var(--upcoming-bar);
  --ink: var(--upcoming-ink);
}

.row-due {
  --tint: var(--due-bg);
  --bar: var(--due-bar);
  --ink: var(--due-ink);
}

.row-overdue {
  --tint: var(--overdue-bg);
  --bar: var(--overdue-bar);
  --ink: var(--overdue-ink);
}

.row-no_history {
  --tint: var(--none-bg);
  --bar: var(--none-bar);
  --ink: var(--none-ink);
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.title {
  display: grid;
  min-width: 0;
}

.title strong {
  font-size: 1.0625rem;
}

.jp,
.other,
.due {
  color: var(--ink);
}

.state {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex: none;
}

.label {
  padding: 2px 8px;
  border: 1.5px solid var(--bar);
  border-radius: 999px;
  color: var(--ink);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.badge {
  background: var(--surface);
  color: var(--text);
}

.reason-text {
  font-weight: 700;
}

.reason::first-letter {
  text-transform: uppercase;
}

.other {
  font-size: 0.875rem;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.actions .btn {
  flex: 1 1 auto;
}

@media (min-width: 768px) {
  .row {
    grid-template-columns: 1fr auto;
    align-items: center;
    column-gap: 16px;
  }

  .head,
  .error {
    grid-column: 1 / -1;
  }

  .actions .btn {
    flex: 0 0 auto;
  }
}
</style>
