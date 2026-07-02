import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Hand } from './Hand'
import type { Card } from '../lib/protocol'

const cards: Card[] = [
  { id: 'c1', rank: '7', suit: 'HEARTS' },
  { id: 'c2', rank: 'JOKER', suit: null },
]

function renderHand(overrides: Partial<Parameters<typeof Hand>[0]> = {}) {
  return render(
    <Hand
      cards={cards}
      selectedIds={[]}
      autoSort={false}
      onToggleAutoSort={vi.fn()}
      onToggleCard={vi.fn()}
      onCardDrop={vi.fn()}
      {...overrides}
    />,
  )
}

describe('Hand', () => {
  it('renders every card with its rank and suit plus the card count', () => {
    renderHand()

    expect(screen.getByText('7♥')).toBeInTheDocument()
    expect(screen.getByText('JOKER')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('marks selected cards as pressed', () => {
    renderHand({ selectedIds: ['c1'] })

    expect(screen.getByRole('button', { name: '7♥' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'JOKER' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('toggles a card on click', async () => {
    const onToggleCard = vi.fn()
    renderHand({ onToggleCard })

    await userEvent.click(screen.getByText('7♥'))

    expect(onToggleCard).toHaveBeenCalledWith('c1')
  })

  it('does not expose manual sort buttons', () => {
    renderHand()

    expect(screen.queryByText('Ранг')).not.toBeInTheDocument()
    expect(screen.queryByText('Масть')).not.toBeInTheDocument()
  })

  it('switches between manual and auto sort modes', async () => {
    const onToggleAutoSort = vi.fn()
    renderHand({ onToggleAutoSort })

    await userEvent.click(screen.getByRole('switch', { name: 'Автосортировка' }))
    expect(onToggleAutoSort).toHaveBeenCalledTimes(1)
  })
})
