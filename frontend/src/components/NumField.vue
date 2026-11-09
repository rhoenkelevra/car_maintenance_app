<script setup lang="ts">
import { ref, watch } from 'vue'

// A numeric text box that opens the phone's number pad and only ever holds a
// valid number: `null` when empty. Decimals are typed with a comma.
const props = defineProps<{ decimal?: boolean }>()
const model = defineModel<number | null>({ required: true })

function toText(value: number | null): string {
  return value === null ? '' : String(value).replace('.', ',')
}

function parse(text: string): number | null {
  if (text === '' || text === ',') return null
  return Number(text.replace(',', '.'))
}

const text = ref(toText(model.value))

watch(model, (value) => {
  if (parse(text.value) !== value) text.value = toText(value)
})

function onInput(event: Event) {
  const input = event.target as HTMLInputElement
  let clean: string
  if (props.decimal) {
    clean = input.value.replace(/\./g, ',').replace(/[^\d,]/g, '')
    const comma = clean.indexOf(',')
    if (comma !== -1) clean = clean.slice(0, comma + 1) + clean.slice(comma + 1).replace(/,/g, '')
  } else {
    clean = input.value.replace(/\D/g, '')
  }
  input.value = clean
  text.value = clean
  model.value = parse(clean)
}
</script>

<template>
  <input
    type="text"
    :inputmode="decimal ? 'decimal' : 'numeric'"
    autocomplete="off"
    :value="text"
    @input="onInput"
  />
</template>
