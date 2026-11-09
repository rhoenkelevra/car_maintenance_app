<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router'
import TabBar from './components/TabBar.vue'
import { flash } from './state'

const route = useRoute()
</script>

<template>
  <TabBar />
  <main class="page">
    <RouterView :key="route.path" />
  </main>
  <p v-if="flash" class="toast" role="status" @click="flash = ''">{{ flash }}</p>
</template>
