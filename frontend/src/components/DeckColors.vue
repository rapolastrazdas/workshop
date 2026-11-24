<script setup lang="ts">
import type { ManaColor } from '../decks'

defineProps<{ colors: ManaColor[]; known: boolean; cardCount: number }>()
const names: Record<ManaColor, string> = { W: 'Balta', U: 'Mėlyna', B: 'Juoda', R: 'Raudona', G: 'Žalia' }
</script>

<template>
  <div class="deck-colors">
    <template v-if="cardCount > 0">
      <ul v-if="colors.length" class="mana-list" aria-label="Kaladės spalvos">
        <li v-for="color in colors" :key="color" class="mana-badge" :class="`mana-${color.toLowerCase()}`" :title="names[color]" :aria-label="names[color]">{{ color }}</li>
      </ul>
      <span v-if="!known" class="muted color-status">Spalvos nenustatytos</span>
      <span v-else-if="!colors.length" class="mana-badge mana-c" title="Bespalvė kaladė" aria-label="Bespalvė kaladė">C</span>
    </template>
  </div>
</template>
