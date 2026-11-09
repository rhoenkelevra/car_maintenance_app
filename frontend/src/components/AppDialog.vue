<script setup lang="ts">
import { onMounted, ref } from 'vue'

// Render with `v-if`: the dialog opens when mounted and asks to be removed with `close`.
defineProps<{ title: string }>()
const emit = defineEmits<{ close: [] }>()

const el = ref<HTMLDialogElement | null>(null)

onMounted(() => el.value?.showModal())

function onClick(event: MouseEvent) {
  // A click on the <dialog> itself is a click on the backdrop.
  if (event.target === el.value) emit('close')
}
</script>

<template>
  <dialog ref="el" class="dialog" @cancel.prevent="emit('close')" @click="onClick">
    <div class="dialog-body">
      <h2>{{ title }}</h2>
      <slot />
    </div>
  </dialog>
</template>

<style scoped>
.dialog {
  width: 100%;
  max-width: 480px;
  max-height: 90dvh;
  margin: auto auto 0;
  padding: 0;
  border: 0;
  border-radius: 16px 16px 0 0;
  background: var(--surface);
  color: var(--text);
  overscroll-behavior: contain;
}

.dialog::backdrop {
  background: rgb(0 0 0 / 0.5);
}

.dialog-body {
  padding: 20px 16px calc(16px + env(safe-area-inset-bottom));
}

h2 {
  margin: 0 0 12px;
  font-size: 1.125rem;
}

@media (min-width: 768px) {
  .dialog {
    margin: auto;
    border-radius: 16px;
  }
}
</style>
