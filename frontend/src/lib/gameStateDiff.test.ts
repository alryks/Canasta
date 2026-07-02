import { describe, expect, it } from 'vitest'
import { diffGameStates } from './gameStateDiff'
import type { GameStateData } from './protocol'

function state(overrides: Partial<GameStateData> = {}): GameStateData {
  return {
    hands: {
      p1: [{ id: 'c1', rank: '7', suit: 'HEARTS' }],
      p2: 10,
    },
    melds: { A: [], B: [] },
    deck_count: 40,
    discard_pile: [],
    discard_count: 0,
    scores: { A: 0, B: 0 },
    thresholds: { A: 50, B: 50 },
    turn_player_id: 'p1',
    turn_phase: 'DRAW',
    must_meld_after_pickup: false,
    melds_created_this_turn: 0,
    pending_penalty: false,
    team_opened: { A: false, B: false },
    turn_accumulator: { A: 0, B: 0 },
    ...overrides,
  }
}

describe('diffGameStates', () => {
  it('detects a deck draw and the viewer card id', () => {
    const result = diffGameStates(
      state(),
      state({
        hands: {
          p1: [
            { id: 'c1', rank: '7', suit: 'HEARTS' },
            { id: 'c2', rank: 'K', suit: 'SPADES' },
          ],
          p2: 10,
        },
        deck_count: 39,
        turn_phase: 'ACT',
      }),
      { viewerId: 'p1', playerNames: { p1: 'Alice' } },
    )

    expect(result.newCardIds).toEqual(['c2'])
    expect(result.events[0]).toMatchObject({
      type: 'draw_deck',
      text: 'Вы взяли карту из колоды',
      cardIds: ['c2'],
    })
  })

  it('detects a discard with card label', () => {
    const result = diffGameStates(
      state({ turn_phase: 'ACT' }),
      state({
        hands: { p1: [], p2: 10 },
        discard_pile: [{ id: 'c1', rank: '7', suit: 'HEARTS' }],
        discard_count: 1,
        turn_phase: 'ACT',
      }),
      { viewerId: 'p2', playerNames: { p1: 'Alice' } },
    )

    expect(result.events[0]).toMatchObject({
      type: 'discard',
      text: 'Alice сбросил 7♥',
      discardCardId: 'c1',
    })
  })

  it('detects a newly closed canasta', () => {
    const openMeld = {
      id: 'm1',
      team_id: 'A',
      kind: 'SET',
      rank_or_suit_anchor: '7',
      slots: [
        { id: 'm1c1', rank: '7', suit: 'HEARTS' },
        { id: 'm1c2', rank: '7', suit: 'SPADES' },
        { id: 'm1c3', rank: '7', suit: 'CLUBS' },
        { id: 'm1c4', rank: '7', suit: 'DIAMONDS' },
        { id: 'm1c5', rank: '7', suit: 'HEARTS' },
        { id: 'm1c6', rank: '7', suit: 'SPADES' },
      ],
    }
    const result = diffGameStates(
      state({ melds: { A: [openMeld], B: [] }, turn_phase: 'ACT' }),
      state({
        melds: {
          A: [
            {
              ...openMeld,
              slots: [...openMeld.slots, { id: 'm1c7', rank: '7', suit: 'CLUBS' }],
            },
          ],
          B: [],
        },
        turn_phase: 'ACT',
      }),
      { viewerId: 'p1', playerNames: { p1: 'Alice' } },
    )

    expect(result.events[0]).toMatchObject({
      type: 'canasta',
      text: 'Вы собрали канасту',
      teamId: 'A',
    })
  })

  it('detects a turn change', () => {
    const result = diffGameStates(
      state({ turn_player_id: 'p1' }),
      state({ turn_player_id: 'p2' }),
      { viewerId: 'p1', playerNames: { p2: 'Bob' } },
    )

    expect(result.events).toContainEqual({
      type: 'turn',
      actorId: 'p2',
      text: 'Ход перешёл к Bob',
    })
  })
})
