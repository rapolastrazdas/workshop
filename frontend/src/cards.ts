export type CardFace = {
  name: string
  type: string
  mana_cost: string
  text: string
  image: string | null
  artist: string | null
  power: string | null
  toughness: string | null
}

export type CardInfo = CardFace & { id: string; faces: CardFace[] }

export type SearchHit = {
  id: string
  name: string
  type: string
  image: string | null
  info: CardInfo
}
