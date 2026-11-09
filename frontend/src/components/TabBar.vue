<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()

const tabs = [
  { to: '/', label: 'Início', icon: 'M3 11.5 12 4l9 7.5M5.5 10v10h13V10' },
  {
    to: '/abastecimentos',
    label: 'Abastecer',
    icon: 'M4 21V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v16M3 21h12M7 7h4v4H7zM14 11h1.5a1.5 1.5 0 0 1 1.5 1.5V17a1.5 1.5 0 0 0 3 0V8.5L17.5 6',
  },
  {
    to: '/manutencoes',
    label: 'Manutenções',
    icon: 'M14.5 6.5a4 4 0 0 0-5 5L3.5 17.5l3 3 6-6a4 4 0 0 0 5-5L15 12l-2.5-.5L12 9z',
  },
  { to: '/itens', label: 'Itens', icon: 'M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01' },
  {
    to: '/carro',
    label: 'Carro',
    icon: 'M5 11l1.6-4.6A2 2 0 0 1 8.5 5h7a2 2 0 0 1 1.9 1.4L19 11M3.5 17v-4a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2v4M3.5 17h17M6 17v2M18 17v2M7.5 14h.01M16.5 14h.01',
  },
]

function isActive(to: string): boolean {
  return to === '/' ? route.path === '/' : route.path === to || route.path.startsWith(`${to}/`)
}
</script>

<template>
  <nav class="tabbar" aria-label="Principal">
    <RouterLink
      v-for="tab in tabs"
      :key="tab.to"
      :to="tab.to"
      class="tab"
      :class="{ active: isActive(tab.to) }"
      :aria-current="isActive(tab.to) ? 'page' : undefined"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="tab.icon" /></svg>
      <span>{{ tab.label }}</span>
    </RouterLink>
  </nav>
</template>

<style scoped>
.tabbar {
  position: fixed;
  inset: auto 0 0 0;
  z-index: 10;
  display: flex;
  background: var(--surface);
  border-top: 1px solid var(--border);
  padding-bottom: env(safe-area-inset-bottom);
}

.tab {
  flex: 1;
  min-width: 0;
  min-height: var(--tabbar-h);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  color: var(--muted);
  text-decoration: none;
  font-size: 0.6875rem;
  font-weight: 600;
}

.tab svg {
  width: 24px;
  height: 24px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.tab.active {
  color: var(--accent);
}

@media (min-width: 768px) {
  .tabbar {
    position: sticky;
    inset: 0 0 auto 0;
    justify-content: center;
    gap: 4px;
    border-top: 0;
    border-bottom: 1px solid var(--border);
    padding: 0 16px;
  }

  .tab {
    flex: 0 0 auto;
    flex-direction: row;
    gap: 8px;
    min-height: 52px;
    padding: 0 14px;
    font-size: 0.9375rem;
    border-bottom: 2px solid transparent;
  }

  .tab svg {
    width: 20px;
    height: 20px;
  }

  .tab.active {
    border-bottom-color: var(--accent);
  }
}
</style>
