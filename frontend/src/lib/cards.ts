import type { Card, Meld } from './protocol'

const SUIT_SYMBOLS: Record<string, string> = {
  SPADES: '♠',
  HEARTS: '♥',
  DIAMONDS: '♦',
  CLUBS: '♣',
}

const RED_SUITS = new Set(['HEARTS', 'DIAMONDS'])

const CARD_POINT_VALUES: Record<string, number> = {
  '2': 10,
  '4': 5,
  '5': 5,
  '6': 5,
  '7': 5,
  '8': 5,
  '9': 5,
  '10': 10,
  J: 10,
  Q: 10,
  K: 10,
  A: 10,
  JOKER: 50,
}

export function suitSymbol(suit: string | null): string {
  if (!suit) return '★'
  return SUIT_SYMBOLS[suit] ?? suit
}

export function isRedSuit(suit: string | null): boolean {
  return suit !== null && RED_SUITS.has(suit)
}

export function cardLabel(card: Card): string {
  if (!card.suit) return card.rank
  return `${card.rank}${SUIT_SYMBOLS[card.suit] ?? card.suit}`
}

export function cardPointsLabel(card: Card): string {
  if (card.rank === '3') {
    return RED_SUITS.has(card.suit ?? '') ? '+100 очков' : '−100 очков'
  }
  return `${CARD_POINT_VALUES[card.rank] ?? 0} очков`
}

export function cardPoints(card: Card): number {
  if (card.rank === '3') return RED_SUITS.has(card.suit ?? '') ? 100 : -100
  return CARD_POINT_VALUES[card.rank] ?? 0
}

export function isWildRank(rank: string): boolean {
  return rank === 'JOKER' || rank === '2'
}

// Mirrors backend MELDABLE_RANKS / SEQUENCE_RANK_ORDER (ace high only).
export const SEQUENCE_RANKS = ['4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

// "SPADES:5" -> where the sequence window starts. Null for sets/wild canastas.
export function parseSequenceAnchor(anchor: string): { suit: string; startIndex: number } | null {
  const [suit, rank] = anchor.split(':')
  if (!suit || !rank) return null
  const startIndex = SEQUENCE_RANKS.indexOf(rank)
  return startIndex === -1 ? null : { suit, startIndex }
}

// Hand-sorting orders. Wilds lead, regular ranks run low to high, and threes
// trail. Suit grouping is preserved by compareForHand below.
const RANK_SORT_ORDER = ['JOKER', '2', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '3']
const SUIT_SORT_ORDER = ['SPADES', 'HEARTS', 'CLUBS', 'DIAMONDS']

function rankSortIndex(card: Card): number {
  const i = RANK_SORT_ORDER.indexOf(card.rank)
  return i === -1 ? RANK_SORT_ORDER.length : i
}

function suitSortIndex(card: Card): number {
  if (card.suit === null) return -1 // jokers first
  const i = SUIT_SORT_ORDER.indexOf(card.suit)
  return i === -1 ? SUIT_SORT_ORDER.length : i
}

export function compareByRank(a: Card, b: Card): number {
  return rankSortIndex(a) - rankSortIndex(b) || suitSortIndex(a) - suitSortIndex(b)
}

export function compareBySuit(a: Card, b: Card): number {
  return suitSortIndex(a) - suitSortIndex(b) || rankSortIndex(a) - rankSortIndex(b)
}

function handGroup(card: Card): number {
  if (isWildRank(card.rank)) return 0
  if (card.rank === '3') return 2
  return 1
}

export function compareForHand(a: Card, b: Card): number {
  return (
    handGroup(a) - handGroup(b) ||
    suitSortIndex(a) - suitSortIndex(b) ||
    rankSortIndex(a) - rankSortIndex(b)
  )
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
