import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Hand } from './Hand'
import type { Card } from '../lib/protocol'

const cards: Card[] = [
  { id: 'c1', rank: '7', suit: 'HEARTS' },
  { id: 'c2', rank: 'JOKER', suit: null },
]

describe('Hand', () => {
  it('renders every card with its rank and suit', () => {
    render(<Hand cards={cards} selectedIds={[]} onToggleCard={vi.fn()} />)

    expect(screen.getByText('7♥')).toBeInTheDocument()
    expect(screen.getByText('JOKER')).toBeInTheDocument()
  })

  it('marks selected cards as pressed', () => {
    render(<Hand cards={cards} selectedIds={['c1']} onToggleCard={vi.fn()} />)

    expect(screen.getByText('7♥')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('JOKER')).toHaveAttribute('aria-pressed', 'false')
  })

  it('toggles a card on click', async () => {
    const onToggleCard = vi.fn()
    render(<Hand cards={cards} selectedIds={[]} onToggleCard={onToggleCard} />)

    await userEvent.click(screen.getByText('7♥'))

    expect(onToggleCard).toHaveBeenCalledWith('c1')
  })
})
