<script setup lang="ts">
import { STATUS_LABEL } from '../describe'
import type { Status } from '../types'

defineProps<{ status: Status }>()
</script>

<template>
  <span class="chip" :class="`chip-${status}`">{{ STATUS_LABEL[status] }}</span>
</template>
