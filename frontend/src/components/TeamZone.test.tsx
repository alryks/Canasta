import { render, screen } from '@testing-library/react'
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
        canStealFrom={false}
        stealTarget={null}
        onSelectStealTarget={vi.fn()}
      />,
    )

    expect(screen.getByText('Ваши комбинации')).toBeInTheDocument()
    expect(screen.getByText('4 ×2')).toBeInTheDocument()
    expect(screen.getByText('9 ×1')).toBeInTheDocument()
  })

  it('labels the opponents zone with the team id', () => {
    render(
      <TeamZone
        teamId="B"
        melds={[]}
        isOwnTeam={false}
        canStealFrom={false}
        stealTarget={null}
        onSelectStealTarget={vi.fn()}
      />,
    )

    expect(screen.getByText('Комбинации соперников')).toBeInTheDocument()
    expect(screen.queryByText('Стол пуст')).not.toBeInTheDocument()
  })

})
