import { describe, expect, it } from 'vitest'
import { compareForHand } from '../lib/cards'
import type { Card } from '../lib/protocol'
import { orderedHand, reorderHand, syncHandOrder } from './handOrderStore'

const c = (id: string, rank: string, suit: string | null = 'HEARTS'): Card => ({
  id,
  rank,
  suit,
})

describe('handOrderStore', () => {
  it('sorts a fresh 13-card deal once', () => {
    const hand = Array.from({ length: 13 }, (_, i) =>
      c(`c${i}`, i === 12 ? '3' : '7', i % 2 === 0 ? 'HEARTS' : 'SPADES'),
    )
    const order = syncHandOrder(hand, [], compareForHand, false)
    const arranged = orderedHand(hand, order)
    expect(arranged.map((card) => card.id)).toEqual(
      [...hand].sort(compareForHand).map((card) => card.id),
    )
  })

  it('appends newly drawn cards to the right without re-sorting', () => {
    const initial = [c('a', '7', 'HEARTS'), c('b', '8', 'HEARTS')]
    const order = syncHandOrder(initial, [], compareForHand, false)

    const afterDraw = [...initial, c('c', '2', 'SPADES')]
    const next = syncHandOrder(afterDraw, order, compareForHand, false)
    expect(next).toEqual([...order, 'c'])
  })

  it('always sorts when auto-sort is enabled', () => {
    const hand = [c('b', '8', 'HEARTS'), c('a', '7', 'HEARTS')]
    const order = syncHandOrder(hand, ['b', 'a'], compareForHand, true)
    expect(order).toEqual([...hand].sort(compareForHand).map((card) => card.id))
  })

  it('reorders a card before another slot', () => {
    expect(reorderHand(['a', 'b', 'c'], 'c', 'a')).toEqual(['c', 'a', 'b'])
  })

  it('detects a new deal when all card ids change', () => {
    const oldOrder = ['x1', 'x2', 'x3']
    const newDeal = Array.from({ length: 13 }, (_, i) => c(`n${i}`, '7', 'HEARTS'))
    const order = syncHandOrder(newDeal, oldOrder, compareForHand, false)
    expect(order).toEqual([...newDeal].sort(compareForHand).map((card) => card.id))
  })
})
