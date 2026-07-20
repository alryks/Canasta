import { describe, expect, it } from 'vitest'
import { cardPointsLabel, compareForHand } from './cards'
import type { Card } from './protocol'

describe('cardPointsLabel', () => {
  it('matches regular and wild card values from the game engine', () => {
    expect(cardPointsLabel({ id: 'c1', rank: '7', suit: 'HEARTS' })).toBe('5 очков')
    expect(cardPointsLabel({ id: 'c2', rank: 'A', suit: 'SPADES' })).toBe('10 очков')
    expect(cardPointsLabel({ id: 'c3', rank: '2', suit: 'CLUBS' })).toBe('10 очков')
    expect(cardPointsLabel({ id: 'c4', rank: 'JOKER', suit: null })).toBe('50 очков')
  })

  it('labels red and black threes as special scoring cards', () => {
    expect(cardPointsLabel({ id: 'r3', rank: '3', suit: 'DIAMONDS' })).toBe('+100 очков')
    expect(cardPointsLabel({ id: 'b3', rank: '3', suit: 'CLUBS' })).toBe('−100 очков')
  })
})

describe('compareForHand', () => {
  it('keeps wilds left and threes right while sorting regular ranks low to high', () => {
    const cards: Card[] = [
      { id: 'ace', rank: 'A', suit: 'HEARTS' },
      { id: 'three', rank: '3', suit: 'HEARTS' },
      { id: 'seven', rank: '7', suit: 'HEARTS' },
      { id: 'two', rank: '2', suit: 'HEARTS' },
      { id: 'four', rank: '4', suit: 'HEARTS' },
      { id: 'joker', rank: 'JOKER', suit: null },
    ]

    expect([...cards].sort(compareForHand).map((card) => card.id)).toEqual([
      'joker',
      'two',
      'four',
      'seven',
      'ace',
      'three',
    ])
  })
})
