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

    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('хост')).toBeInTheDocument()
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

    expect(screen.getByText(/Bob · офлайн/)).toBeInTheDocument()
  })

  it('lets the host assign an unseated player via modal', async () => {
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

    await userEvent.click(screen.getAllByText('Назначить')[0])
    await userEvent.click(screen.getByRole('button', { name: 'Bob' }))

    expect(onAssignSeat).toHaveBeenCalledWith('p2', 1)
  })

  it('lets the host replace an occupied seat', async () => {
    const alice = player({ id: 'p1', name: 'Alice', seat: 0, is_host: true })
    const bob = player({ id: 'p2', name: 'Bob', seat: 1 })
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

    await userEvent.click(screen.getAllByText('Сменить')[0])
    await userEvent.click(screen.getByRole('button', { name: /Bob/ }))

    expect(onAssignSeat).toHaveBeenCalledWith('p2', 0)
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
    expect(screen.queryByText('Назначить')).not.toBeInTheDocument()
    expect(screen.queryByText(/Добавить бота/)).not.toBeInTheDocument()
  })

  it('lets the host add a bot from the assign modal', async () => {
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

    await userEvent.click(screen.getAllByText('Назначить')[1])
    await userEvent.click(screen.getByRole('button', { name: 'Добавить бота' }))
    expect(onAddBot).toHaveBeenCalledWith(1)
  })

  it('shows bot status without emoji', () => {
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

    expect(screen.getByText('бот')).toBeInTheDocument()
    expect(screen.queryByText(/🤖/)).not.toBeInTheDocument()
  })
})
