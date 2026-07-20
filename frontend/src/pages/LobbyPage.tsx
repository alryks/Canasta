import { useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { LobbySettingsPanel } from '../components/LobbySettingsPanel'
import { SeatGrid } from '../components/SeatGrid'
import { useConnectionStore } from '../stores/connectionStore'
import { useLobbyStore } from '../stores/lobbyStore'

const REQUIRED_SEATS = 4

export function LobbyPage({ devBootstrapAllowed = true }: { devBootstrapAllowed?: boolean }) {
  const { gameId = '' } = useParams()
  const send = useConnectionStore((s) => s.send)
  const status = useConnectionStore((s) => s.status)
  const playerId = useConnectionStore((s) => s.playerId)
  const players = useLobbyStore((s) => s.players)
  const hostId = useLobbyStore((s) => s.hostId)
  const settings = useLobbyStore((s) => s.settings)
  const lastDevCommand = useRef<string | null>(null)

  const inviteLink = `${window.location.origin}/join/${gameId}`
  const isHost = playerId !== null && playerId === hostId
  const seatedCount = players.filter((p) => p.seat !== null).length
  const canStart = isHost && seatedCount === REQUIRED_SEATS

  useEffect(() => {
    if (
      !import.meta.env.DEV ||
      !devBootstrapAllowed ||
      status !== 'open' ||
      !isHost ||
      playerId === null
    )
      return

    const me = players.find((player) => player.id === playerId)
    let command: string | null = null
    let type: string | null = null
    let data: Record<string, unknown> = {}

    if (me?.seat === null) {
      command = `assign-host:${playerId}`
      type = 'assign_seat'
      data = { player_id: playerId, seat: 0 }
    } else {
      const occupiedSeats = new Set(
        players.flatMap((player) => (player.seat === null ? [] : [player.seat])),
      )
      const emptySeat = [0, 1, 2, 3].find((seat) => !occupiedSeats.has(seat))
      if (emptySeat !== undefined) {
        command = `add-bot:${emptySeat}`
        type = 'add_bot'
        data = { seat: emptySeat }
      } else if (seatedCount === REQUIRED_SEATS) {
        command = 'start-game'
        type = 'start_game'
      }
    }

    if (command === null || type === null || lastDevCommand.current === command) return
    lastDevCommand.current = command
    send(type, data)
  }, [devBootstrapAllowed, isHost, playerId, players, seatedCount, send, status])

  const statusDotClass =
    status === 'open'
      ? 'is-open'
      : status === 'connecting'
        ? 'is-connecting'
        : status === 'closed' || status === 'error'
          ? 'is-closed'
          : ''

  return (
    <main className="page-shell">
      <div className="panel" style={{ width: 'min(640px, 100%)' }}>
        <h1 className="brand-title">Лобби</h1>
        <p className="status-line">
          <span className={`status-dot ${statusDotClass}`} />
          Статус соединения: {status}
        </p>

        <div className="invite-row">
          <span>Ссылка для друзей:</span>
          <code className="invite-code">{inviteLink}</code>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => navigator.clipboard.writeText(inviteLink)}
          >
            Скопировать
          </button>
        </div>

        <h2>Места за столом</h2>
        <SeatGrid
          players={players}
          hostId={hostId}
          isHost={isHost}
          onAssignSeat={(assignedPlayerId, seat) =>
            send('assign_seat', { player_id: assignedPlayerId, seat })
          }
          onAddBot={(seat) => send('add_bot', { seat })}
        />

        <h2>Настройки</h2>
        <LobbySettingsPanel
          targetScore={settings.targetScore}
          discardVisibility={settings.discardVisibility}
          isHost={isHost}
          onChange={(change) => send('set_lobby_settings', change)}
        />

        {isHost && (
          <button
            type="button"
            className="btn btn-primary"
            disabled={!canStart}
            onClick={() => send('start_game', {})}
          >
            Начать игру
          </button>
        )}
      </div>
    </main>
  )
}
