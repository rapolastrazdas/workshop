<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api, ApiError, auth } from '../auth'
import { rememberImport, type DeckWrite } from '../decks'
import { router } from '../router'
import { showNotice } from '../notices'

const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
const nameInput = ref<HTMLInputElement>()
const name = ref('')
const cardList = ref('')
const nameError = ref('')
const listError = ref('')
const message = ref('')
const busy = ref(false)
let previousFocus: HTMLElement | null = null

onMounted(() => {
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  dialog.value?.showModal()
  nameInput.value?.focus()
})

onBeforeUnmount(() => {
  dialog.value?.close()
  previousFocus?.focus()
})

watch(() => auth.session, (session) => { if (!session) emit('close') })

function cancel(event?: Event) {
  event?.preventDefault()
  if (!busy.value) emit('close')
}

async function create() {
  if (busy.value) return
  nameError.value = ''
  listError.value = ''
  message.value = ''
  if (Array.from(name.value.trim()).length > 100) {
    nameError.value = 'Pavadinimas negali būti ilgesnis nei 100 simbolių.'
    nameInput.value?.focus()
    return
  }
  busy.value = true
  try {
    const result = await api<DeckWrite>('/decks', { method: 'POST', body: JSON.stringify({ name: name.value, card_list: cardList.value }) })
    rememberImport(result.deck.id, result.import_result)
    showNotice(result.import_result ? `Importuotų kortų: ${result.import_result.imported}.` : '', `/kalades/${result.deck.id}`)
    emit('close')
    await router.push({ name: 'deck', params: { id: result.deck.id } })
  } catch (error) {
    if (error instanceof ApiError && error.status === 422 && typeof error.detail === 'object' && error.detail !== null && 'errors' in error.detail) {
      const errors = error.detail.errors as Record<string, string>
      nameError.value = errors.name || ''
      listError.value = errors.card_list || ''
      await nextTick()
      if (nameError.value) nameInput.value?.focus()
    } else if (!(error instanceof ApiError && error.status === 401)) {
      message.value = error instanceof Error ? error.message : 'Nepavyko sukurti kaladės. Bandykite dar kartą.'
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <dialog ref="dialog" class="modal-dialog" aria-labelledby="new-deck-title" @cancel="cancel">
    <div class="dialog-header">
      <h2 id="new-deck-title">Nauja kaladė</h2>
      <button class="dialog-close" type="button" aria-label="Uždaryti" :disabled="busy" @click="cancel()">×</button>
    </div>
    <form novalidate :aria-busy="busy" @submit.prevent="create">
      <div class="field">
        <label for="deck-name">Pavadinimas (nebūtinas)</label>
        <input id="deck-name" ref="nameInput" v-model="name" type="text" :disabled="busy" :aria-invalid="Boolean(nameError)"
          :aria-describedby="nameError ? 'deck-name-error deck-name-help' : 'deck-name-help'" />
        <p id="deck-name-help" class="field-help">Iki 100 simbolių. Neįrašius pavadinimo, jis bus suteiktas automatiškai.</p>
        <p v-if="nameError" id="deck-name-error" class="field-error" role="alert">{{ nameError }}</p>
      </div>
      <div class="field">
        <label for="deck-card-list">Kortų sąrašas (nebūtinas)</label>
        <p id="deck-list-help" class="field-help">Viena korta eilutėje, pvz., „4 Lightning Bolt“. Leidimo kodas ir kolekcinis numeris, pvz., „1 Sol Ring (C21) 263“, nebūtini. Svarstomas kortas rašykite po eilute „Svarstomos“.</p>
        <textarea id="deck-card-list" v-model="cardList" rows="8" :disabled="busy" :aria-invalid="Boolean(listError)"
          :aria-describedby="listError ? 'deck-list-error deck-list-help' : 'deck-list-help'" placeholder="4 Lightning Bolt&#10;&#10;Svarstomos&#10;1 Sol Ring"></textarea>
        <p v-if="listError" id="deck-list-error" class="field-error" role="alert">{{ listError }}</p>
      </div>
      <p v-if="message" class="error-banner" role="alert">{{ message }}</p>
      <div class="dialog-actions">
        <button class="button" type="button" :disabled="busy" @click="cancel()">Atšaukti</button>
        <button class="button button-primary" type="submit" :disabled="busy">{{ busy ? 'Kuriama…' : 'Sukurti' }}</button>
      </div>
    </form>
  </dialog>
</template>
