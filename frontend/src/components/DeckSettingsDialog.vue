<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api, ApiError, auth } from '../auth'
import type { DeckSummary, DeckWrite } from '../decks'
import { showNotice } from '../notices'
import DeleteDeckDialog from './DeleteDeckDialog.vue'

const props = defineProps<{ deck: DeckSummary }>()
const emit = defineEmits<{ close: []; saved: [result: DeckWrite] }>()
const dialog = ref<HTMLDialogElement>()
const nameInput = ref<HTMLInputElement>()
const name = ref(props.deck.name)
const cardList = ref('')
const nameError = ref('')
const listError = ref('')
const message = ref('')
const busy = ref(false)
const deleting = ref(false)
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
  if (!busy.value) emit('close')
}

async function save() {
  if (busy.value) return
  nameError.value = ''
  listError.value = ''
  message.value = ''
  const length = Array.from(name.value.trim()).length
  if (length < 1 || length > 100) {
    nameError.value = 'Pavadinimą turi sudaryti nuo 1 iki 100 simbolių.'
    nameInput.value?.focus()
    return
  }
  busy.value = true
  try {
    const result = await api<DeckWrite>(`/decks/${props.deck.id}`, {
      method: 'PUT', body: JSON.stringify({ name: name.value, card_list: cardList.value }),
    })
    showNotice(result.import_result ? `Pakeitimai išsaugoti. Importuotų kortų: ${result.import_result.imported}.` : 'Pakeitimai išsaugoti.')
    emit('saved', result)
  } catch (error) {
    if (error instanceof ApiError && error.status === 422 && typeof error.detail === 'object' && error.detail !== null && 'errors' in error.detail) {
      const errors = error.detail.errors as Record<string, string>
      nameError.value = errors.name || ''
      listError.value = errors.card_list || ''
      await nextTick()
      if (nameError.value) nameInput.value?.focus()
    } else if (!(error instanceof ApiError && error.status === 401)) {
      message.value = error instanceof Error ? error.message : 'Nepavyko išsaugoti pakeitimų. Bandykite dar kartą.'
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <dialog ref="dialog" class="modal-dialog" aria-labelledby="settings-title" @cancel="cancel">
    <div class="dialog-header">
      <h2 id="settings-title">Kaladės nustatymai</h2>
      <button class="dialog-close" type="button" aria-label="Uždaryti" :disabled="busy" @click="cancel()">×</button>
    </div>
    <form novalidate :aria-busy="busy" @submit.prevent="save">
      <div class="field">
        <label for="settings-name">Pavadinimas</label>
        <input id="settings-name" ref="nameInput" v-model="name" type="text" required :disabled="busy" :aria-invalid="Boolean(nameError)"
          :aria-describedby="nameError ? 'settings-name-error' : undefined" />
        <p v-if="nameError" id="settings-name-error" class="field-error" role="alert">{{ nameError }}</p>
      </div>
      <div class="field">
        <label for="settings-import">Kortų importas (nebūtinas)</label>
        <p id="settings-import-help" class="field-help">Kortos bus pridėtos prie kaladės. Viena korta eilutėje: kiekis ir pavadinimas. Leidimo kodas ir kolekcinis numeris, pvz., „1 Sol Ring (C21) 263“, nebūtini.</p>
        <textarea id="settings-import" v-model="cardList" rows="4" :disabled="busy" :aria-invalid="Boolean(listError)"
          :aria-describedby="listError ? 'settings-import-error settings-import-help' : 'settings-import-help'"
          placeholder="1 Bygone Bishop&#10;1 Trail of Evidence"></textarea>
        <p v-if="listError" id="settings-import-error" class="field-error" role="alert">{{ listError }}</p>
      </div>
      <p v-if="message" class="error-banner" role="alert">{{ message }}</p>
      <div class="dialog-actions">
        <button class="button" type="button" :disabled="busy" @click="cancel()">Atšaukti</button>
        <button class="button button-primary" type="submit" :disabled="busy">{{ busy ? 'Saugoma…' : 'Išsaugoti' }}</button>
      </div>
    </form>
    <div class="deck-deletion-section">
      <div>
        <h3>Kaladės ištrynimas</h3>
        <p class="field-help">Ištrintos kaladės atkurti negalima.</p>
      </div>
      <button class="button button-danger" type="button" :disabled="busy" @click="deleting = true">Ištrinti kaladę</button>
    </div>
    <DeleteDeckDialog v-if="deleting" :deck="deck" @close="deleting = false" />
  </dialog>
</template>
