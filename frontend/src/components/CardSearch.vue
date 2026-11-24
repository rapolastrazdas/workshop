<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../auth'
defineProps<{ collapsible?: boolean }>()
type Hit = { id: string; name: string; type: string; image: string | null }
const query = ref('')
const cards = ref<Hit[]>([])
const total = ref(0)
const visible = ref(8)
const hidden = ref(false)
const busy = ref(false)
const message = ref('')
let submitted = ''
let page = 0
let more = false
const displayed = computed(() => cards.value.slice(0, visible.value))
async function fetchPage() {
  const result = await api<{ cards: Hit[]; total: number; more: boolean }>(
    '/cards/search?q=' + encodeURIComponent(submitted) + '&page=' + (page + 1), {}, false)
  page++
  cards.value.push(...result.cards)
  total.value = result.total
  more = result.more
}
async function run(append: boolean) {
  if (busy.value) return
  if (!append) {
    submitted = query.value.trim()
    page = 0
    cards.value = []
    total.value = 0
    visible.value = 8
    hidden.value = false
    more = false
  }
  message.value = ''
  if (!submitted) return
  busy.value = true
  try {
    if (!append || (visible.value + 8 > cards.value.length && more)) await fetchPage()
    if (append) visible.value += 8
    if (!total.value) message.value = 'Kortų nerasta.'
  } catch {
    message.value = 'Kortų paieška laikinai neveikia. Bandykite vėliau.'
  } finally { busy.value = false }
}
</script>
<template>
  <section aria-label="Kortų paieška">
    <form @submit.prevent="run(false)">
      <label>Kortų paieška (Sintaksė) <input v-model="query" maxlength="500" type="search"></label>
      <button class="button" :disabled="busy || !query.trim()">Ieškoti</button>
    </form>
    <p v-if="message" role="status">{{ message }}</p>
    <button v-if="collapsible && total" class="button" @click="hidden = !hidden">{{ hidden ? 'Rodyti' : 'Slėpti' }} rezultatus ({{ total }})</button>
    <div v-if="!hidden">
      <ul v-if="displayed.length" class="search-results">
        <li v-for="card in displayed" :key="card.id">
          <img v-if="card.image" :src="card.image" alt="" width="90" loading="lazy">
          <strong>{{ card.name }}</strong><span>{{ card.type }}</span>
          <slot name="actions" :card="card" />
        </li>
      </ul>
      <button v-if="visible < cards.length || more" class="button" :disabled="busy" @click="run(true)">Rodyti daugiau</button>
    </div>
  </section>
</template>
<style scoped>
.search-results { display: grid; grid-template-columns: repeat(auto-fill,minmax(145px,1fr)); gap: 1rem; list-style: none; padding: 0; }
.search-results li { display: grid; align-content: start; gap: .4rem; }
</style>
