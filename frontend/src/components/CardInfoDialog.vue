<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../auth'
import type { CardInfo } from '../cards'

const props = defineProps<{ cardId: string; initial?: CardInfo; editor?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
const info = ref(props.initial)
const loading = ref(false)
const error = ref('')
const controller = new AbortController()
const faces = computed(() => {
  const card = info.value
  if (!card) return []
  return card.faces.length
    ? card.faces.map((face, index) => ({
        ...face,
        image: face.image ?? (index === 0 ? card.image : null),
        artist: face.artist ?? card.artist,
      }))
    : [card]
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    info.value = await api<CardInfo>(`/cards/${encodeURIComponent(props.cardId)}`, { signal: controller.signal }, false)
  } catch (cause) {
    if (!controller.signal.aborted) error.value = cause instanceof Error ? cause.message : 'Nepavyko gauti kortos informacijos.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  dialog.value?.showModal()
  if (!info.value) void load()
})

onBeforeUnmount(() => {
  controller.abort()
  dialog.value?.close()
})
</script>

<template>
  <dialog ref="dialog" class="modal-dialog card-info-dialog" aria-labelledby="card-info-title"
    @cancel.prevent="emit('close')">
    <div class="dialog-header">
      <h2 id="card-info-title">Kortos informacija</h2>
      <button class="dialog-close" type="button" aria-label="Uždaryti langą" @click="emit('close')">×</button>
    </div>
    <p v-if="loading" role="status">Kraunama kortos informacija…</p>
    <div v-else-if="error">
      <p class="error-banner" role="alert">{{ error }}</p>
      <button class="button" type="button" @click="load">Bandyti dar kartą</button>
    </div>
    <template v-else-if="info">
      <h3 v-if="faces.length > 1" class="card-info-full-name">{{ info.name }}</h3>
      <section v-for="(face, index) in faces" :key="index" class="card-info-face">
        <img v-if="face.image" :src="face.image" :alt="face.name" width="240">
        <p v-else class="muted">Paveikslėlio nėra.</p>
        <div>
          <h3>{{ face.name }} <span v-if="face.mana_cost" class="muted">{{ face.mana_cost }}</span></h3>
          <p v-if="face.type">{{ face.type }}</p>
          <p class="card-info-text">{{ face.text }}</p>
          <p v-if="face.power !== null && face.toughness !== null">{{ face.power }}/{{ face.toughness }}</p>
          <p v-if="face.artist" class="muted">Iliustracija: {{ face.artist }}</p>
        </div>
      </section>
      <slot />
    </template>
    <button class="button" type="button" disabled aria-describedby="similar-cards-note">Rasti panašias</button>
    <p id="similar-cards-note" class="muted">Panašių kortų paieška dar neprieinama.</p>
    <div v-if="editor" class="card-info-analysis">
      <section>
        <h3>Įgalina ir įgalinama</h3>
        <p class="muted">Kortų sąveikų analizė dar neprieinama.</p>
      </section>
      <section>
        <h3>Ištraukimo tikimybė</h3>
        <p class="muted">Ištraukimo tikimybė dar neskaičiuojama.</p>
      </section>
    </div>
  </dialog>
</template>

<style scoped>
.card-info-dialog { width: 900px; }
.card-info-face { display: grid; grid-template-columns: minmax(120px, 240px) minmax(0, 1fr); gap: 20px; margin: 0 0 20px; }
.card-info-face img { width: 100%; height: auto; border-radius: 8px; }
.card-info-face h3, .card-info-full-name { margin: 0 0 10px; }
.card-info-text { white-space: pre-line; overflow-wrap: anywhere; }
.card-info-analysis { border-top: 1px solid #e2e8f0; display: flex; flex-wrap: wrap; gap: 12px 32px; }
@media (max-width: 540px) {
  .card-info-face { grid-template-columns: minmax(0, 1fr); }
  .card-info-face img { max-width: 240px; }
}
</style>
