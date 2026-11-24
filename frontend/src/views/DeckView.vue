<script setup lang="ts">
import CardSearch from "../components/CardSearch.vue"
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { api, ApiError } from '../auth'
import { consumeImport, type DeckCard, type DeckDetail, type DeckWrite, type ImportResult } from '../decks'
import DeckColors from '../components/DeckColors.vue'
import ImportResultDialog from '../components/ImportResultDialog.vue'
import DeckSettingsDialog from '../components/DeckSettingsDialog.vue'

const route = useRoute()
const deck = ref<DeckDetail | null>(null)
const loading = ref(true)
const error = ref('')
const notFound = ref(false)
const report = ref<ImportResult | null>(null)
const settingsOpen = ref(false)
let latestRequest = 0
type ListName = DeckCard['list_name']
type Action = 'add' | 'decrease' | 'remove'
const saving = ref(false)
const editError = ref('')

async function edit(oracle_id: string, list_name: ListName, action: Action) {
  const current = deck.value
  if (!current || saving.value || loading.value) return
  saving.value = true
  editError.value = ''
  const request = ++latestRequest
  try {
    const updated = await api<DeckDetail>('/decks/' + current.id + '/cards', {
      method: 'POST', body: JSON.stringify({ oracle_id, list_name, action }),
    })
    if (request === latestRequest) deck.value = updated
  } catch (cause) {
    if (request === latestRequest) editError.value = cause instanceof ApiError && cause.status === 422
      ? cause.message : 'Pakeitimo išsaugoti nepavyko, jis atšauktas. Bandykite dar kartą.'
  } finally { saving.value = false }
}

const cards = computed(() => [...(deck.value?.cards ?? [])].sort(
  (left, right) => (left.name ?? '').localeCompare(right.name ?? '', 'lt') ||
    left.oracle_id.localeCompare(right.oracle_id),
))
const maybeboard = computed(() => cards.value.filter(card => card.list_name === 'maybeboard'))
const maybeboardCount = computed(() => maybeboard.value.reduce((sum, card) => sum + card.quantity, 0))
const mainGroups = computed(() => {
  const labels = ['0', '1', '2', '3', '4', '5', '6+', 'Žemės', 'Nežinoma manos vertė']
  const groups = labels.map(label => ({ label, count: 0, cards: [] as DeckCard[] }))
  for (const card of cards.value) {
    if (card.list_name !== 'main') continue
    const index = card.is_land ? 7 : card.mana_value == null ? 8 : Math.min(6, Math.floor(card.mana_value))
    groups[index].cards.push(card)
    groups[index].count += card.quantity
  }
  return groups.filter(group => group.count > 0)
})
const cardGroups = computed(() => [
  ...mainGroups.value.map(group => ({ ...group, heading: 'h3' })),
  { label: 'Svarstomos kortos', heading: 'h2', count: maybeboardCount.value, cards: maybeboard.value },
])

function settingsSaved(result: DeckWrite) {
  settingsOpen.value = false
  imported(result)
}

function imported(result: DeckWrite) {
  if (deck.value?.id !== result.deck.id) return
  deck.value = { ...deck.value, ...result.deck }
  report.value = result.import_result
  void load()
}

async function load() {
  const request = ++latestRequest
  loading.value = true
  error.value = ''
  notFound.value = false
  try {
    const result = await api<DeckDetail>(`/decks/${encodeURIComponent(String(route.params.id))}`)
    if (request === latestRequest) deck.value = result
  } catch (cause) {
    if (request !== latestRequest) return
    if (cause instanceof ApiError && cause.status === 404) {
      deck.value = null
      notFound.value = true
    }
    else if (!(cause instanceof ApiError && cause.status === 401)) {
      error.value = cause instanceof Error ? cause.message : 'Nepavyko atidaryti kaladės. Bandykite dar kartą.'
    }
  } finally {
    if (request === latestRequest) loading.value = false
  }
}

watch(() => route.params.id, (id) => {
  if (typeof id !== 'string') return
  deck.value = null
  report.value = consumeImport(Number(id))
  settingsOpen.value = false
  void load()
}, { immediate: true })
</script>

<template>
  <section class="content-area" :aria-busy="loading" aria-label="Kaladės redaktorius">
    <RouterLink class="back-link" to="/mano-kalades">Mano kaladės</RouterLink>
    <p v-if="loading && !deck" class="muted" role="status">Kraunama kaladė…</p>
    <h1 v-else-if="notFound">Kaladė nerasta</h1>
    <div v-else-if="error && !deck" class="load-error">
      <p class="error-banner" role="alert">{{ error }}</p>
      <button class="button" @click="load">Bandyti dar kartą</button>
    </div>
    <template v-else-if="deck">
      <CardSearch>
        <template #actions="{ card }">
          <button class="button" :disabled="saving || loading" @click="edit(card.id, 'main', 'add')">+ Pagrindinis</button>
          <button class="button" :disabled="saving || loading" @click="edit(card.id, 'maybeboard', 'add')">+ Svarstomos</button>
        </template>
      </CardSearch>
      <p v-if="editError" role="alert" class="error-banner">{{ editError }}</p>
      <ImportResultDialog v-if="report && (report.unrecognized_lines.length || report.skipped_main)" :deck-id="deck.id" :deck-name="deck.name" :result="report" @close="report = null" @updated="imported" />
      <DeckSettingsDialog v-if="settingsOpen" :deck="deck" @close="settingsOpen = false" @saved="settingsSaved" />
      <div class="decks-heading">
        <h1>{{ deck.name }}</h1>
        <button class="button" :disabled="loading" @click="settingsOpen = true">Nustatymai</button>
      </div>
      <p class="muted">Kortų: {{ deck.card_count }}</p>
      <DeckColors :colors="deck.colors" :known="deck.colors_known" :card-count="deck.card_count" />
      <p v-if="error" class="error-banner" role="alert">{{ error }} <button class="button" @click="load">Bandyti dar kartą</button></p>
      <div class="deck-composition">
        <h2>Pagrindinės kortos</h2>
        <p v-if="!loading && !error && cards.length === 0" class="muted">
          Kaladėje dar nėra kortų. Ieškokite kortų arba importuokite kortų sąrašą.
        </p>
        <section v-for="group in cardGroups" :key="group.label" class="deck-card-group">
          <component :is="group.heading">{{ group.label }} ({{ group.count }})</component>
          <ul v-if="group.cards.length" class="deck-card-list">
            <li v-for="card in group.cards" :key="card.oracle_id">
              <span>{{ card.quantity }}×</span>
              <span>{{ card.name ?? 'Nežinoma korta' }}</span>
              <span class="deck-mana-cost">{{ card.mana_cost === null ? '—' : card.mana_cost }}</span>
              <div class="card-actions">
                <button :disabled="saving || loading" aria-label="Padidinti kiekį" @click="edit(card.oracle_id, card.list_name, 'add')">+</button>
                <button :disabled="saving || loading" aria-label="Sumažinti kiekį" @click="edit(card.oracle_id, card.list_name, 'decrease')">−</button>
                <button :disabled="saving || loading" @click="edit(card.oracle_id, card.list_name, 'remove')">Pašalinti</button>
              </div>
            </li>
          </ul>
        </section>
      </div>
    </template>
  </section>
</template>
