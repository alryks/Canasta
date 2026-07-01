import { useParams } from 'react-router-dom'
import { LobbySettingsPanel } from '../components/LobbySettingsPanel'
import { SeatGrid } from '../components/SeatGrid'
import { useConnectionStore } from '../stores/connectionStore'
import { useLobbyStore } from '../stores/lobbyStore'

const REQUIRED_SEATS = 4

export function LobbyPage() {
  const { gameId = '' } = useParams()
  const send = useConnectionStore((s) => s.send)
  const status = useConnectionStore((s) => s.status)
  const playerId = useConnectionStore((s) => s.playerId)
  const players = useLobbyStore((s) => s.players)
  const hostId = useLobbyStore((s) => s.hostId)
  const settings = useLobbyStore((s) => s.settings)

  const inviteLink = `${window.location.origin}/join/${gameId}`
  const isHost = playerId !== null && playerId === hostId
  const seatedCount = players.filter((p) => p.seat !== null).length
  const canStart = isHost && seatedCount === REQUIRED_SEATS

  return (
    <main>
      <h1>Лобби</h1>
      <p>
        Ссылка для друзей: <code>{inviteLink}</code>{' '}
        <button
          type="button"
          onClick={() => navigator.clipboard.writeText(inviteLink)}
        >
          Скопировать
        </button>
      </p>
      <p>Статус соединения: {status}</p>

      <SeatGrid
        players={players}
        hostId={hostId}
        isHost={isHost}
        onAssignSeat={(assignedPlayerId, seat) =>
          send('assign_seat', { player_id: assignedPlayerId, seat })
        }
      />

      <LobbySettingsPanel
        targetScore={settings.targetScore}
        discardVisibility={settings.discardVisibility}
        isHost={isHost}
        onChange={(change) => send('set_lobby_settings', change)}
      />

      {isHost && (
        <button
          type="button"
          disabled={!canStart}
          onClick={() => send('start_game', {})}
        >
          Начать игру
        </button>
      )}
    </main>
  )
}
