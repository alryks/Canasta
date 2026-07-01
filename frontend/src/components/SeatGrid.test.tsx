import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SeatGrid } from './SeatGrid'
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

describe('SeatGrid', () => {
  it('shows an empty seat as free for a non-host viewer', () => {
    render(
      <SeatGrid players={[]} hostId={null} isHost={false} onAssignSeat={vi.fn()} />,
    )
    expect(screen.getAllByText(/свободно/)).toHaveLength(4)
  })

  it('places a seated player in their seat and marks the host', () => {
    const alice = player({ id: 'p1', name: 'Alice', seat: 0, is_host: true })
    render(
      <SeatGrid
        players={[alice]}
        hostId="p1"
        isHost={false}
        onAssignSeat={vi.fn()}
      />,
    )

    const seats = screen.getByRole('list', { name: 'seats' })
    expect(seats).toHaveTextContent('Alice (хост) — в сети')
    expect(screen.getAllByText(/свободно/)).toHaveLength(3)
  })

  it('lists joined players who have not been assigned a seat yet', () => {
    const bob = player({ id: 'p2', name: 'Bob', seat: null, connected: false })
    render(
      <SeatGrid players={[bob]} hostId="p1" isHost={false} onAssignSeat={vi.fn()} />,
    )

    const unseated = screen.getByRole('list', { name: 'unseated' })
    expect(unseated).toHaveTextContent('Bob — офлайн')
  })

  it('lets the host assign an unseated player to an empty seat', async () => {
    const alice = player({ id: 'p1', name: 'Alice', seat: 0, is_host: true })
    const bob = player({ id: 'p2', name: 'Bob', seat: null })
    const onAssignSeat = vi.fn()
    render(
      <SeatGrid
        players={[alice, bob]}
        hostId="p1"
        isHost
        onAssignSeat={onAssignSeat}
      />,
    )

    await userEvent.selectOptions(
      screen.getByLabelText('Посадить на место 2'),
      'p2',
    )

    expect(onAssignSeat).toHaveBeenCalledWith('p2', 1)
  })

  it('does not offer seat assignment controls to non-host viewers', () => {
    render(
      <SeatGrid players={[]} hostId="p1" isHost={false} onAssignSeat={vi.fn()} />,
    )
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })
})
