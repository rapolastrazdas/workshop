export type ManaColor = 'W' | 'U' | 'B' | 'R' | 'G'

export type DeckSummary = {
  id: number
  name: string
  card_count: number
  colors: ManaColor[]
  colors_known: boolean
}

export type DeckList = { count: number; decks: DeckSummary[] }

const plural = new Intl.PluralRules('lt')
export function deckCountLabel(count: number): string {
  const form = plural.select(count)
  return `${count} ${form === 'one' ? 'kaladė' : form === 'few' ? 'kaladės' : 'kaladžių'}`
}
