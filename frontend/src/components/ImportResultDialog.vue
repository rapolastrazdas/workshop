<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api, ApiError, auth } from '../auth'
import type { DeckWrite, ImportResult } from '../decks'
import { showNotice } from '../notices'

const props = defineProps<{ deckId: number; deckName: string; result: ImportResult }>()
const emit = defineEmits<{ close: []; updated: [result: DeckWrite] }>()
const dialog = ref<HTMLDialogElement>()
const corrected = ref('')
const busy = ref(false)
const message = ref('')
let previousFocus: HTMLElement | null = null

watch(() => props.result, (result) => {
  const main = result.unrecognized_lines.filter((line) => line.list_name === 'main').map((line) => line.text)
  const maybe = result.unrecognized_lines.filter((line) => line.list_name === 'maybeboard').map((line) => line.text)
  corrected.value = [...main, ...(maybe.length ? ['Svarstomos', ...maybe] : [])].join('\n')
}, { immediate: true })

watch(() => auth.session, (session) => { if (!session) emit('close') })

onMounted(() => {
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  dialog.value?.showModal()
})
onBeforeUnmount(() => { dialog.value?.close(); previousFocus?.focus() })

function close(event?: Event) {
  event?.preventDefault()
  if (!busy.value) emit('close')
}

async function retry() {
  if (busy.value || !corrected.value.trim()) return
  busy.value = true
  message.value = ''
  try {
    const result = await api<DeckWrite>(`/decks/${props.deckId}/import`, {
      method: 'POST', body: JSON.stringify({ card_list: corrected.value }),
    })
    showNotice(`Importuotų kortų: ${result.import_result?.imported ?? 0}.`)
    emit('updated', result)
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 401)) {
      message.value = error instanceof Error ? error.message : 'Nepavyko importuoti kortų. Bandykite dar kartą.'
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <dialog ref="dialog" class="modal-dialog import-result-dialog" aria-labelledby="import-title" @cancel="close">
    <div class="dialog-header">
      <h2 id="import-title">Importo rezultatas</h2>
      <button class="dialog-close" type="button" aria-label="Uždaryti langą" :disabled="busy" @click="close()">×</button>
    </div>
    <p v-if="result.imported > 0">Atpažintos kortos jau įrašytos į kaladę „{{ deckName }}“.</p>
    <p v-else>Šiuo bandymu į kaladę „{{ deckName }}“ kortų neimportuota.</p>
    <p v-if="result.skipped_main" role="status">Viršyta 500 pagrindinių kortų riba. Neimportuotų kortų: {{ result.skipped_main }}.</p>
    <form :aria-busy="busy" @submit.prevent="retry">
      <div v-if="result.unrecognized_lines.length" class="field">
        <p id="import-help">Neatpažintų eilučių: {{ result.unrecognized_lines.length }}. Pataisykite jas arba praleiskite.</p>
        <label for="corrected-lines">Neatpažintos eilutės</label>
        <textarea id="corrected-lines" v-model="corrected" rows="5" aria-describedby="import-help corrected-lines-help" :disabled="busy"></textarea>
        <p id="corrected-lines-help" class="field-help">Viena korta eilutėje: kiekis ir pavadinimas.</p>
      </div>
      <p v-if="message" class="error-banner" role="alert">{{ message }}</p>
      <div class="dialog-actions">
        <button class="button" type="button" :disabled="busy" @click="close()">Uždaryti</button>
        <button v-if="result.unrecognized_lines.length" class="button button-primary" type="submit" :disabled="busy || !corrected.trim()">{{ busy ? 'Importuojama…' : 'Importuoti pataisytas' }}</button>
      </div>
    </form>
  </dialog>
</template>
