<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, errorMessage } from '../api'
import { fmtDate, fmtKm, fmtLitres, fmtYen, fmtYenPerLitre } from '../format'
import type { FuelLog } from '../types'

const logs = ref<FuelLog[]>([])
const loading = ref(true)
const error = ref('')

function perLitre(log: FuelLog): string {
  if (log.price_total === null || !log.litres) return ''
  return fmtYenPerLitre(log.price_total / log.litres)
}

onMounted(async () => {
  try {
    const list = await api.listFuel()
    logs.value = list.sort((a, b) => b.date.localeCompare(a.date) || b.km - a.km)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page-head">
    <h1>Abastecimentos</h1>
    <RouterLink class="btn btn-primary" to="/abastecimentos/novo">+ Abastecimento</RouterLink>
  </div>

  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-else-if="loading" class="muted">Carregando…</p>
  <div v-else-if="!logs.length" class="empty">
    <strong>Nenhum abastecimento</strong>
    Registre o primeiro quando encher o tanque.
  </div>
  <ul v-else class="list">
    <li v-for="log in logs" :key="log.id">
      <RouterLink class="list-link" :to="`/abastecimentos/${log.id}`">
        <div class="line">
          <strong>{{ fmtDate(log.date) }}</strong>
          <span class="num">{{ fmtKm(log.km) }}</span>
        </div>
        <div class="line small muted num">
          <span>
            {{ log.litres !== null ? fmtLitres(log.litres) : '— L' }}
            <template v-if="!log.full_tank"> (parcial)</template>
            · {{ log.price_total !== null ? fmtYen(log.price_total) : '¥ —' }}
          </span>
          <span>{{ perLitre(log) }}</span>
        </div>
        <p v-if="log.station" class="small muted">{{ log.station }}</p>
      </RouterLink>
    </li>
  </ul>
</template>
