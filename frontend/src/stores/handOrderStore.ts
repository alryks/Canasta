import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Card } from '../lib/protocol'

interface HandOrderStore {
  order: string[]
  autoSort: boolean
  setOrder: (ids: string[]) => void
  setAutoSort: (enabled: boolean) => void
  toggleAutoSort: () => void
  reset: () => void
}

export const useHandOrderStore = create<HandOrderStore>()(
  persist(
    (set, get) => ({
      order: [],
      autoSort: false,
      setOrder: (ids) => set({ order: ids }),
      setAutoSort: (autoSort) => set({ autoSort }),
      toggleAutoSort: () => set({ autoSort: !get().autoSort }),
      reset: () => set({ order: [] }),
    }),
    {
      name: 'canast-hand-prefs',
      partialize: (state) => ({ autoSort: state.autoSort }),
    },
  ),
)

const DEAL_HAND_SIZE = 13

function isFreshDeal(cards: Card[], order: string[]): boolean {
  if (cards.length !== DEAL_HAND_SIZE) return false
  if (order.length === 0) return true
  const handIds = new Set(cards.map((c) => c.id))
  return order.every((id) => !handIds.has(id))
}

/** Keep client hand order between draws: sort once per deal, then append new cards on the right. */
export function syncHandOrder(
  cards: Card[],
  order: string[],
  sort: (a: Card, b: Card) => number,
  autoSort: boolean,
): string[] {
  if (cards.length === 0) return []

  if (autoSort) {
    return [...cards].sort(sort).map((c) => c.id)
  }

  if (isFreshDeal(cards, order)) {
    return [...cards].sort(sort).map((c) => c.id)
  }

  const handIds = new Set(cards.map((c) => c.id))
  const next = order.filter((id) => handIds.has(id))
  const placed = new Set(next)
  for (const card of cards) {
    if (!placed.has(card.id)) {
      next.push(card.id)
      placed.add(card.id)
    }
  }
  return next
}

export function orderedHand(cards: Card[], order: string[]): Card[] {
  const byId = new Map(cards.map((c) => [c.id, c]))
  const arranged: Card[] = []
  for (const id of order) {
    const card = byId.get(id)
    if (card) {
      arranged.push(card)
      byId.delete(id)
    }
  }
  return [...arranged, ...byId.values()]
}

export function reorderHand(order: string[], draggedId: string, beforeId: string): string[] {
  if (draggedId === beforeId) return order
  const without = order.filter((id) => id !== draggedId)
  const insertAt = without.indexOf(beforeId)
  if (insertAt === -1) return order
  return [...without.slice(0, insertAt), draggedId, ...without.slice(insertAt)]
}
