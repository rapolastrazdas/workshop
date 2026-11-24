export type ManaColor = 'W' | 'U' | 'B' | 'R' | 'G'

export type DeckSummary = {
  id: number
  name: string
  card_count: number
  colors: ManaColor[]
  colors_known: boolean
}

export type DeckList = { count: number; decks: DeckSummary[] }

export type ImportResult = {
  imported: number
  unrecognized_lines: { text: string; list_name: 'main' | 'maybeboard' }[]
  skipped_main: number
}

export type DeckWrite = { deck: DeckSummary; import_result: ImportResult | null }

let pendingImport: { deckId: number; result: ImportResult } | null = null

export function rememberImport(deckId: number, result: ImportResult | null) {
  pendingImport = result ? { deckId, result } : null
}

export function consumeImport(deckId: number): ImportResult | null {
  const result = pendingImport?.deckId === deckId ? pendingImport.result : null
  pendingImport = null
  return result
}

const plural = new Intl.PluralRules('lt')
export function deckCountLabel(count: number): string {
  const form = plural.select(count)
  return `${count} ${form === 'one' ? 'kaladė' : form === 'few' ? 'kaladės' : 'kaladžių'}`
}
