import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { SeatList } from '../components/SeatList'
import { isLobbyStateMessage } from '../lib/protocol'
import { loadSession } from '../lib/session'
import { useConnectionStore } from '../stores/connectionStore'
import { useLobbyStore } from '../stores/lobbyStore'

export function LobbyPage() {
  const { gameId = '' } = useParams()
  const navigate = useNavigate()
  const connect = useConnectionStore((s) => s.connect)
  const disconnect = useConnectionStore((s) => s.disconnect)
  const status = useConnectionStore((s) => s.status)
  const applyLobbyState = useLobbyStore((s) => s.applyLobbyState)
  const players = useLobbyStore((s) => s.players)
  const hostId = useLobbyStore((s) => s.hostId)
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
      <SeatList players={players} hostId={hostId} />
    </main>
  )
}
