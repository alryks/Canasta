import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { TeamZone } from './TeamZone'
import type { Meld } from '../lib/protocol'

const melds: Meld[] = [
  {
    id: 'm1',
    team_id: 'A',
    kind: 'SET',
    rank_or_suit_anchor: '4',
    slots: [
      { id: 'c1', rank: '4', suit: 'HEARTS' },
      { id: 'c2', rank: '4', suit: 'SPADES' },
    ],
  },
  {
    id: 'm2',
    team_id: 'A',
    kind: 'SET',
    rank_or_suit_anchor: '9',
    slots: [{ id: 'c3', rank: '9', suit: 'CLUBS' }],
  },
]

describe('TeamZone', () => {
  it('renders one MeldStack per meld under the team heading', () => {
    render(
      <TeamZone
        teamId="A"
        melds={melds}
        isOwnTeam
        canAddCards={false}
        onAddToMeld={vi.fn()}
        canStealFrom={false}
        stealTarget={null}
        onSelectStealTarget={vi.fn()}
      />,
    )

    expect(screen.getByText('Команда A')).toBeInTheDocument()
    expect(screen.getByText(/SET 4/)).toBeInTheDocument()
    expect(screen.getByText(/SET 9/)).toBeInTheDocument()
  })

  it('routes onAddToMeld with the clicked meld id', async () => {
    const onAddToMeld = vi.fn()
    render(
      <TeamZone
        teamId="A"
        melds={melds}
        isOwnTeam
        canAddCards
        onAddToMeld={onAddToMeld}
        canStealFrom={false}
        stealTarget={null}
        onSelectStealTarget={vi.fn()}
      />,
    )

    const addButtons = screen.getAllByText('Добавить сюда')
    await userEvent.click(addButtons[1])
    expect(onAddToMeld).toHaveBeenCalledWith('m2')
  })
})
