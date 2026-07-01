import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SeatList } from './SeatList'
import type { LobbyPlayer } from '../lib/protocol'

function player(overrides: Partial<LobbyPlayer>): LobbyPlayer {
  return {
    id: 'p1',
    name: 'Alice',
    seat: null,
    team_id: null,
    connected: true,
    is_host: false,
    ...overrides,
  }
}

describe('SeatList', () => {
  it('shows an empty seat as free', () => {
    render(<SeatList players={[]} hostId={null} />)
    expect(screen.getAllByText(/свободно/)).toHaveLength(4)
  })

  it('places a seated player in their seat and marks the host', () => {
    const alice = player({ id: 'p1', name: 'Alice', seat: 0, is_host: true })
    render(<SeatList players={[alice]} hostId="p1" />)

    const seats = screen.getByRole('list', { name: 'seats' })
    expect(seats).toHaveTextContent('Alice (хост) — в сети')
    expect(screen.getAllByText(/свободно/)).toHaveLength(3)
  })

  it('lists joined players who have not been assigned a seat yet', () => {
    const bob = player({ id: 'p2', name: 'Bob', seat: null, connected: false })
    render(<SeatList players={[bob]} hostId="p1" />)

    const unseated = screen.getByRole('list', { name: 'unseated' })
    expect(unseated).toHaveTextContent('Bob — офлайн')
  })
})
