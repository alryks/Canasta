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
    is_bot: false,
    ...overrides,
  }
}

describe('SeatGrid', () => {
  it('shows an empty seat as free for a non-host viewer', () => {
    render(
      <SeatGrid
        players={[]}
        hostId={null}
        isHost={false}
        onAssignSeat={vi.fn()}
        onAddBot={vi.fn()}
      />,
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
        onAddBot={vi.fn()}
      />,
    )

    const seats = screen.getByRole('list', { name: 'seats' })
    expect(seats).toHaveTextContent('Alice (хост) — в сети')
    expect(screen.getAllByText(/свободно/)).toHaveLength(3)
  })

  it('lists joined players who have not been assigned a seat yet', () => {
    const bob = player({ id: 'p2', name: 'Bob', seat: null, connected: false })
    render(
      <SeatGrid
        players={[bob]}
        hostId="p1"
        isHost={false}
        onAssignSeat={vi.fn()}
        onAddBot={vi.fn()}
      />,
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
        onAddBot={vi.fn()}
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
      <SeatGrid
        players={[]}
        hostId="p1"
        isHost={false}
        onAssignSeat={vi.fn()}
        onAddBot={vi.fn()}
      />,
    )
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(screen.queryByText(/Добавить бота/)).not.toBeInTheDocument()
  })

  it('lets the host add a bot to an empty seat', async () => {
    const onAddBot = vi.fn()
    render(
      <SeatGrid
        players={[]}
        hostId="p1"
        isHost
        onAssignSeat={vi.fn()}
        onAddBot={onAddBot}
      />,
    )

    const addBotButtons = screen.getAllByText('🤖 Добавить бота')
    expect(addBotButtons).toHaveLength(4)

    await userEvent.click(addBotButtons[1])
    expect(onAddBot).toHaveBeenCalledWith(1)
  })

  it('shows a bot badge instead of online/offline for a bot player', () => {
    const bot = player({ id: 'p3', name: 'Бот 2', seat: 1, is_bot: true, connected: true })
    render(
      <SeatGrid
        players={[bot]}
        hostId="p1"
        isHost
        onAssignSeat={vi.fn()}
        onAddBot={vi.fn()}
      />,
    )

    const seats = screen.getByRole('list', { name: 'seats' })
    expect(seats).toHaveTextContent('Бот 2 — бот')
    expect(screen.getByText('🤖 бот')).toBeInTheDocument()
    expect(screen.queryByText('в сети')).not.toBeInTheDocument()
  })
})
