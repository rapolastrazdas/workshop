<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api, ApiError, auth } from '../auth'
import type { DeckSummary } from '../decks'
import { showNotice } from '../notices'
import { router } from '../router'

const props = defineProps<{ deck: DeckSummary }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
const nameInput = ref<HTMLInputElement>()
const name = ref('')
const touched = ref(false)
const serverError = ref('')
const message = ref('')
const busy = ref(false)
const matches = computed(() => name.value === props.deck.name)
const nameError = computed(() => serverError.value || (touched.value && !matches.value
  ? 'Įvestas pavadinimas nesutampa su kaladės pavadinimu.' : ''))
let previousFocus: HTMLElement | null = null

onMounted(() => {
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  dialog.value?.showModal()
  nameInput.value?.focus()
})
onBeforeUnmount(() => { dialog.value?.close(); previousFocus?.focus() })
watch(() => auth.session, (session) => { if (!session) emit('close') })

function cancel(event?: Event) {
  event?.preventDefault()
  event?.stopPropagation()
  if (!busy.value) emit('close')
}

function edited() {
  touched.value = true
  serverError.value = ''
}

async function remove() {
  touched.value = true
  if (busy.value || !matches.value || serverError.value) return
  busy.value = true
  message.value = ''
  try {
    await api(`/decks/${props.deck.id}`, { method: 'DELETE', body: JSON.stringify({ name: name.value }) })
    showNotice('Kaladė ištrinta.', '/mano-kalades')
    await router.replace({ name: 'decks' })
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      serverError.value = 'Įvestas pavadinimas nesutampa su kaladės pavadinimu.'
      nameInput.value?.focus()
    } else if (!(error instanceof ApiError && error.status === 401)) {
      message.value = error instanceof Error ? error.message : 'Nepavyko ištrinti kaladės. Bandykite dar kartą.'
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <dialog ref="dialog" class="modal-dialog" aria-labelledby="delete-deck-title" aria-describedby="delete-deck-description" @cancel="cancel">
    <div class="dialog-header">
      <h2 id="delete-deck-title">Ištrinti kaladę?</h2>
      <button class="dialog-close" type="button" aria-label="Uždaryti" :disabled="busy" @click="cancel()">×</button>
    </div>
    <p id="delete-deck-description">Kaladė „<strong>{{ deck.name }}</strong>“ ir visos jos kortos bus ištrintos. Šio veiksmo atšaukti negalima. Norėdami patvirtinti, įveskite kaladės pavadinimą.</p>
    <form novalidate :aria-busy="busy" @submit.prevent="remove">
      <div class="field">
        <label for="delete-deck-name">Kaladės pavadinimas</label>
        <input id="delete-deck-name" ref="nameInput" v-model="name" type="text" autocomplete="off" required :disabled="busy"
          :aria-invalid="Boolean(nameError)" :aria-describedby="nameError ? 'delete-deck-name-error' : undefined" @input="edited" />
        <p v-if="nameError" id="delete-deck-name-error" class="field-error" role="alert">{{ nameError }}</p>
      </div>
      <p v-if="message" class="error-banner" role="alert">{{ message }}</p>
      <div class="dialog-actions">
        <button class="button" type="button" :disabled="busy" @click="cancel()">Atšaukti</button>
        <button class="button button-destructive" type="submit" :disabled="busy || !matches || Boolean(serverError)">{{ busy ? 'Trinama…' : 'Ištrinti' }}</button>
      </div>
    </form>
  </dialog>
</template>
