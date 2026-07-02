import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MeldStack } from './MeldStack'
import type { Meld } from '../lib/protocol'
import { useDragStore } from '../stores/dragStore'

const openMeld: Meld = {
  id: 'm1',
  team_id: 'A',
  kind: 'SET',
  rank_or_suit_anchor: '4',
  slots: [
    { id: 'c1', rank: '4', suit: 'HEARTS' },
    { id: 'c2', rank: '4', suit: 'SPADES' },
    { id: 'c3', rank: '4', suit: 'CLUBS' },
  ],
}

const dirtySequence: Meld = {
  id: 'm2',
  team_id: 'B',
  kind: 'SEQUENCE',
  rank_or_suit_anchor: 'SPADES:5',
  slots: [
    { id: 'c4', rank: '5', suit: 'SPADES' },
    { id: 'w1', rank: 'JOKER', suit: null },
    { id: 'c5', rank: '7', suit: 'SPADES' },
  ],
}

describe('MeldStack', () => {
  it('shows every card of the meld with a caption', () => {
    render(
      <MeldStack
        meld={openMeld}
        isOwnTeam
        canStealFrom={false}
        isStealTarget={() => false}
        onSelectStealTarget={vi.fn()}
      />,
    )

    expect(screen.getByText('4♥')).toBeInTheDocument()
    expect(screen.getByText('4♠')).toBeInTheDocument()
    expect(screen.getByText('4♣')).toBeInTheDocument()
    expect(screen.getByText('4 ×3')).toBeInTheDocument()
  })

  it('captions a sequence with its suit and rank range', () => {
    render(
      <MeldStack
        meld={dirtySequence}
        isOwnTeam={false}
        canStealFrom={false}
        isStealTarget={() => false}
        onSelectStealTarget={vi.fn()}
      />,
    )

    expect(screen.getByText('♠ 5–7')).toBeInTheDocument()
  })

  it('makes opponent wild cards steal targets when allowed', async () => {
    const onSelectStealTarget = vi.fn()
    render(
      <MeldStack
        meld={dirtySequence}
        isOwnTeam={false}
        canStealFrom
        isStealTarget={() => false}
        onSelectStealTarget={onSelectStealTarget}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'JOKER' }))
    expect(onSelectStealTarget).toHaveBeenCalledWith('w1')
  })

  it('does not show an add button on opponent melds', () => {
    render(
      <MeldStack
        meld={openMeld}
        isOwnTeam={false}
        canStealFrom={false}
        isStealTarget={() => false}
        onSelectStealTarget={vi.fn()}
      />,
    )

    expect(screen.queryByText('Доложить сюда')).not.toBeInTheDocument()
  })

  const closedCanasta: Meld = {
    id: 'm3',
    team_id: 'A',
    kind: 'SET',
    rank_or_suit_anchor: 'K',
    slots: [
      { id: 'k1', rank: 'K', suit: 'HEARTS' },
      { id: 'k2', rank: 'K', suit: 'SPADES' },
      { id: 'k3', rank: 'K', suit: 'CLUBS' },
      { id: 'k4', rank: 'K', suit: 'DIAMONDS' },
      { id: 'k5', rank: 'K', suit: 'HEARTS' },
      { id: 'k6', rank: 'K', suit: 'SPADES' },
      { id: 'w2', rank: '2', suit: 'HEARTS' },
    ],
  }

  it('renders a completed canasta collapsed into a pile', () => {
    render(
      <MeldStack
        meld={closedCanasta}
        isOwnTeam
        canStealFrom={false}
        isStealTarget={() => false}
        onSelectStealTarget={vi.fn()}
      />,
    )

    // only the top card of the pile is visible, plus the count and badge
    expect(screen.getByText('×7')).toBeInTheDocument()
    expect(screen.getByText('Грязная канаста')).toBeInTheDocument()
    expect(screen.queryByText('K♥')).not.toBeInTheDocument()
  })

  it('expands a collapsed canasta on click and lets it collapse back', async () => {
    render(
      <MeldStack
        meld={closedCanasta}
        isOwnTeam={false}
        canStealFrom
        isStealTarget={() => false}
        onSelectStealTarget={vi.fn()}
      />,
    )

    await userEvent.click(
      screen.getByRole('button', { name: /показать карты/i }),
    )
    // all cards visible, wild is a steal target
    expect(screen.getAllByText('K♥')).toHaveLength(2)
    expect(screen.getByRole('button', { name: '2♥' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /свернуть/i }))
    expect(screen.queryByText('K♥')).not.toBeInTheDocument()
  })

  it('keeps a collapsed canasta folded while dragging from hand', () => {
    render(
      <MeldStack
        meld={closedCanasta}
        isOwnTeam={false}
        canStealFrom
        isStealTarget={() => false}
        onSelectStealTarget={vi.fn()}
      />,
    )

    useDragStore.getState().startDrag('hand-card', 'hand', 0, 0)
    expect(screen.queryByText('K♥')).not.toBeInTheDocument()
    useDragStore.getState().endDrag()
  })

  it('exposes a steal drop zone on a collapsed canasta with one wild', () => {
    render(
      <MeldStack
        meld={closedCanasta}
        isOwnTeam={false}
        canStealFrom
        isStealTarget={() => false}
        onSelectStealTarget={vi.fn()}
      />,
    )

    expect(
      screen.getByRole('button', { name: /показать карты/i }),
    ).toHaveAttribute('data-drop-zone', 'wild:m3:w2')
  })
})
