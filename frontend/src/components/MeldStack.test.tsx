import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MeldStack } from './MeldStack'
import type { Meld } from '../lib/protocol'

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

describe('MeldStack', () => {
  it('shows the top card and count, collapsed by default', () => {
    render(
      <MeldStack
        meld={openMeld}
        isOwnTeam
        canAddCards={false}
        onAddToMeld={vi.fn()}
        canStealFrom={false}
        isStealTarget={() => false}
        onSelectStealTarget={vi.fn()}
      />,
    )

    expect(screen.getByText(/SET 4 — 4♣ ×3/)).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('expands to show every slot on click', async () => {
    render(
      <MeldStack
        meld={openMeld}
        isOwnTeam
        canAddCards={false}
        onAddToMeld={vi.fn()}
        canStealFrom={false}
        isStealTarget={() => false}
        onSelectStealTarget={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByText(/SET 4/))
    expect(screen.getByRole('list')).toBeInTheDocument()
    expect(screen.getByText('4♥')).toBeInTheDocument()
  })

  it('only offers "add to meld" for the viewer\'s own team when cards are selected', () => {
    render(
      <MeldStack
        meld={openMeld}
        isOwnTeam={false}
        canAddCards
        onAddToMeld={vi.fn()}
        canStealFrom={false}
        isStealTarget={() => false}
        onSelectStealTarget={vi.fn()}
      />,
    )

    expect(screen.queryByText('Добавить сюда')).not.toBeInTheDocument()
  })

  it('calls onAddToMeld when adding to an own-team meld', async () => {
    const onAddToMeld = vi.fn()
    render(
      <MeldStack
        meld={openMeld}
        isOwnTeam
        canAddCards
        onAddToMeld={onAddToMeld}
        canStealFrom={false}
        isStealTarget={() => false}
        onSelectStealTarget={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByText('Добавить сюда'))
    expect(onAddToMeld).toHaveBeenCalled()
  })
})
