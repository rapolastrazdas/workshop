<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <section v-if="route.name === 'decks'" class="decks-placeholder" aria-labelledby="decks-title">
    <h1 id="decks-title">Mano kaladės</h1>
  </section>
  <section v-else-if="route.name === 'deck'" class="decks-placeholder">
    <h1>Kaladė nerasta.</h1>
  </section>
  <div v-else class="guest-placeholder" aria-label="Pagrindinis puslapis"></div>
</template>
