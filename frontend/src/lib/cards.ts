import type { Card, Meld } from './protocol'

const SUIT_SYMBOLS: Record<string, string> = {
  SPADES: '♠',
  HEARTS: '♥',
  DIAMONDS: '♦',
  CLUBS: '♣',
}

export function cardLabel(card: Card): string {
  if (!card.suit) return card.rank
  return `${card.rank}${SUIT_SYMBOLS[card.suit] ?? card.suit}`
}

export function isWildRank(rank: string): boolean {
  return rank === 'JOKER' || rank === '2'
}

export type CanastaStatus = 'open' | 'clean' | 'dirty' | 'wild'

// The server never sends is_closed/canasta_type (plan section 9 mentions
// them, but the WS payload in ws/serialization.py only sends raw slots) --
// both are trivially derivable from the slots the client already has.
export function canastaStatus(meld: Meld): CanastaStatus {
  const cards = meld.slots.filter((c): c is Card => c !== null)
  if (cards.length < 7) return 'open'
  const wildCount = cards.filter((c) => isWildRank(c.rank)).length
  if (wildCount === 0) return 'clean'
  if (wildCount === cards.length) return 'wild'
  return 'dirty'
}
