import { isWildRank, SEQUENCE_RANKS, suitSymbol } from './cards'
import type { Card } from './protocol'

export interface CreateWildPlacement {
  lowLabel: string
  highLabel: string
}

function missingSequenceRanks(startIndex: number, size: number, naturalIndices: Set<number>) {
  const ranks: string[] = []
  for (let i = startIndex; i < startIndex + size; i += 1) {
    if (!naturalIndices.has(i)) ranks.push(SEQUENCE_RANKS[i])
  }
  return ranks
}

function wildPlacementLabel(ranks: string[], suit: string | null): string {
  const symbol = suitSymbol(suit)
  return ranks.map((rank) => `${rank}${symbol}`).join(', ')
}

// Mirrors backend _build_sequence_slots enough to tell the player exactly
// which rank newly selected wild cards will occupy when creating a sequence.
export function createWildPlacementOptions(cards: Card[]): CreateWildPlacement | null {
  const wilds = cards.filter((c) => isWildRank(c.rank))
  const naturals = cards.filter((c) => !isWildRank(c.rank) && c.rank !== '3')
  if (wilds.length === 0 || naturals.length < 2 || wilds.length > naturals.length) return null
  const suits = new Set(naturals.map((c) => c.suit))
  if (suits.size !== 1) return null
  const indices = naturals.map((c) => SEQUENCE_RANKS.indexOf(c.rank))
  if (indices.some((i) => i === -1)) return null
  const naturalIndices = new Set(indices)
  if (naturalIndices.size !== indices.length) return null
  const low = Math.min(...indices)
  const high = Math.max(...indices)
  if (cards.length < high - low + 1) return null

  const startMin = Math.max(0, high - (cards.length - 1))
  const startMax = Math.min(low, SEQUENCE_RANKS.length - cards.length)
  if (startMin >= startMax) return null

  const suit = naturals[0]?.suit ?? null
  return {
    lowLabel: wildPlacementLabel(missingSequenceRanks(startMin, cards.length, naturalIndices), suit),
    highLabel: wildPlacementLabel(missingSequenceRanks(startMax, cards.length, naturalIndices), suit),
  }
}
