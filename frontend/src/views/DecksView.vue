<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, ApiError } from '../auth'
import { deckCountLabel, type DeckList } from '../decks'
import DeckColors from '../components/DeckColors.vue'

const data = ref<DeckList | null>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api<DeckList>('/decks')
  } catch (cause) {
    if (!(cause instanceof ApiError && cause.status === 401)) {
      error.value = cause instanceof Error ? cause.message : 'Nepavyko gauti kaladžių. Bandykite dar kartą.'
    }
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="content-area" aria-labelledby="decks-title" :aria-busy="loading">
    <div class="decks-heading">
      <div class="heading-with-count">
        <h1 id="decks-title">Mano kaladės</h1>
        <span v-if="data && !loading && !error" class="muted" data-testid="deck-count">{{ deckCountLabel(data.count) }}</span>
      </div>
      <button class="button button-primary" disabled title="Kaladžių kūrimas dar nepasiekiamas.">+ Nauja kaladė</button>
    </div>
    <p v-if="loading" class="muted" role="status">Kraunamos kaladės…</p>
    <div v-else-if="error" class="load-error">
      <p class="error-banner" role="alert">{{ error }}</p>
      <button class="button" @click="load">Bandyti dar kartą</button>
    </div>
    <template v-else-if="data">
      <div v-if="!data.count" class="empty-decks">
        <h2>Dar neturite kaladžių</h2>
        <p class="muted">Sukurkite savo pirmąją kaladę.</p>
      </div>
      <ul v-else class="deck-grid" aria-label="Mano kaladžių sąrašas">
        <li v-for="deck in data.decks" :key="deck.id">
          <RouterLink class="deck-card" :to="{ name: 'deck', params: { id: deck.id } }" :aria-label="`${deck.name}. Kortų: ${deck.card_count}.`">
            <h2>{{ deck.name }}</h2>
            <p class="muted">Kortų: {{ deck.card_count }}</p>
            <DeckColors :colors="deck.colors" :known="deck.colors_known" :card-count="deck.card_count" />
          </RouterLink>
        </li>
      </ul>
    </template>
  </section>
</template>
