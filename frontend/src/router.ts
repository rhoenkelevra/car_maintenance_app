import { createRouter, createWebHistory } from 'vue-router'
import { ensureCar } from './state'
import CarView from './views/CarView.vue'
import FuelFormView from './views/FuelFormView.vue'
import FuelListView from './views/FuelListView.vue'
import HomeView from './views/HomeView.vue'
import ItemFormView from './views/ItemFormView.vue'
import ItemsListView from './views/ItemsListView.vue'
import MaintenanceFormView from './views/MaintenanceFormView.vue'
import MaintenanceListView from './views/MaintenanceListView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/abastecimentos', component: FuelListView },
    { path: '/abastecimentos/novo', component: FuelFormView },
    { path: '/abastecimentos/:id', component: FuelFormView, props: true },
    { path: '/manutencoes', component: MaintenanceListView },
    { path: '/manutencoes/nova', component: MaintenanceFormView },
    { path: '/manutencoes/:id', component: MaintenanceFormView, props: true },
    { path: '/itens', component: ItemsListView },
    { path: '/itens/novo', component: ItemFormView },
    { path: '/itens/:id', component: ItemFormView, props: true },
    { path: '/carro', component: CarView },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
})

// Every other endpoint answers 409 until a car exists, so register it first.
router.beforeEach(async (to) => {
  if (to.path === '/carro') return true
  try {
    if ((await ensureCar()) === null) return { path: '/carro' }
  } catch {
    // API unreachable: let the screen load and show its own error.
  }
  return true
})

/** After a save or delete: back to where the user came from, else to `fallback`. */
export function goBack(fallback: string): void {
  const state = window.history.state as { back?: string | null } | null
  if (state?.back) router.back()
  else void router.replace(fallback)
}
