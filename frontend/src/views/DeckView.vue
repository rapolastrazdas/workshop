<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { api, ApiError } from '../auth'
import { consumeImport, type DeckSummary, type DeckWrite, type ImportResult } from '../decks'
import DeckColors from '../components/DeckColors.vue'
import ImportResultDialog from '../components/ImportResultDialog.vue'

const route = useRoute()
const deck = ref<DeckSummary | null>(null)
const loading = ref(true)
const error = ref('')
const notFound = ref(false)
const report = ref<ImportResult | null>(consumeImport(Number(route.params.id)))

function imported(result: DeckWrite) {
  deck.value = result.deck
  report.value = result.import_result
}

async function load() {
  loading.value = true
  error.value = ''
  notFound.value = false
  try {
    deck.value = await api<DeckSummary>(`/decks/${encodeURIComponent(String(route.params.id))}`)
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 404) notFound.value = true
    else if (!(cause instanceof ApiError && cause.status === 401)) {
      error.value = cause instanceof Error ? cause.message : 'Nepavyko atidaryti kaladės. Bandykite dar kartą.'
    }
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="content-area" :aria-busy="loading" aria-label="Kaladės redaktorius">
    <RouterLink class="back-link" to="/mano-kalades">Mano kaladės</RouterLink>
    <p v-if="loading" class="muted" role="status">Kraunama kaladė…</p>
    <h1 v-else-if="notFound">Kaladė nerasta</h1>
    <div v-else-if="error" class="load-error">
      <p class="error-banner" role="alert">{{ error }}</p>
      <button class="button" @click="load">Bandyti dar kartą</button>
    </div>
    <template v-else-if="deck">
      <ImportResultDialog v-if="report && (report.unrecognized_lines.length || report.skipped_main)" :deck-id="deck.id" :result="report" @close="report = null" @updated="imported" />
      <h1>{{ deck.name }}</h1>
      <p class="muted">Kortų: {{ deck.card_count }}</p>
      <DeckColors :colors="deck.colors" :known="deck.colors_known" :card-count="deck.card_count" />
      <div class="editor-placeholder">
        <h2>Pagrindinės kortos</h2>
        <p v-if="deck.card_count === 0" class="muted">Kaladėje dar nėra kortų.</p>
      </div>
    </template>
  </section>
</template>
