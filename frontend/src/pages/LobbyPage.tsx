import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { LobbySettingsPanel } from '../components/LobbySettingsPanel'
import { SeatGrid } from '../components/SeatGrid'
import { isLobbyStateMessage } from '../lib/protocol'
import { loadSession } from '../lib/session'
import { useConnectionStore } from '../stores/connectionStore'
import { useLobbyStore } from '../stores/lobbyStore'

const REQUIRED_SEATS = 4

export function LobbyPage() {
  const { gameId = '' } = useParams()
  const navigate = useNavigate()
  const connect = useConnectionStore((s) => s.connect)
  const send = useConnectionStore((s) => s.send)
  const disconnect = useConnectionStore((s) => s.disconnect)
  const status = useConnectionStore((s) => s.status)
  const playerId = useConnectionStore((s) => s.playerId)
  const applyLobbyState = useLobbyStore((s) => s.applyLobbyState)
  const players = useLobbyStore((s) => s.players)
  const hostId = useLobbyStore((s) => s.hostId)
  const settings = useLobbyStore((s) => s.settings)
  const [gameStarted, setGameStarted] = useState(false)

  useEffect(() => {
    const session = loadSession(gameId)
    if (!session) {
      navigate(`/join/${gameId}`, { replace: true })
      return
    }

    connect(gameId, session.playerId, session.sessionToken, (message) => {
      if (isLobbyStateMessage(message)) {
        applyLobbyState(message.data)
      } else {
        // any non-lobby broadcast means the game already started -- the
        // real game board lands in phase 7
        setGameStarted(true)
      }
    })

    return () => disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId])

  const inviteLink = `${window.location.origin}/join/${gameId}`
  const isHost = playerId !== null && playerId === hostId
  const seatedCount = players.filter((p) => p.seat !== null).length
  const canStart = isHost && seatedCount === REQUIRED_SEATS

  if (gameStarted) {
    return (
      <main>
        <h1>Игра уже началась</h1>
        <p>Игровой стол появится здесь позже.</p>
      </main>
    )
  }

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
