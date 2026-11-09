<script setup lang="ts">
import AppDialog from './AppDialog.vue'

defineProps<{
  title: string
  message: string
  confirmLabel: string
  busy?: boolean
  error?: string
}>()
const emit = defineEmits<{ close: []; confirm: [] }>()
</script>

<template>
  <AppDialog :title="title" @close="emit('close')">
    <p class="message">{{ message }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="dialog-actions">
      <button type="button" class="btn" @click="emit('close')">Cancelar</button>
      <button type="button" class="btn btn-danger" :disabled="busy" @click="emit('confirm')">
        {{ confirmLabel }}
      </button>
    </div>
  </AppDialog>
</template>

<style scoped>
.message {
  margin: 0 0 12px;
}
</style>
