import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  isActionErrorMessage,
  isDealResultMessage,
  isGameOverMessage,
  isGameStateMessage,
  isLobbyStateMessage,
} from '../lib/protocol'
import { loadSession } from '../lib/session'
import { useConnectionStore } from '../stores/connectionStore'
import { useGameStore } from '../stores/gameStore'
import { useLobbyStore } from '../stores/lobbyStore'
import { GamePage } from './GamePage'
import { LobbyPage } from './LobbyPage'

// Owns the single WS connection for a game and dispatches every incoming
// message to the right store, then picks lobby vs. board by whether a
// game_state has ever arrived -- on a reconnect into an already-started
// game, the server sends game_state directly with no lobby_state at all.
export function GameRoute() {
  const { gameId = '' } = useParams()
  const navigate = useNavigate()
  const connect = useConnectionStore((s) => s.connect)
  const disconnect = useConnectionStore((s) => s.disconnect)
  const applyLobbyState = useLobbyStore((s) => s.applyLobbyState)
  const applyGameState = useGameStore((s) => s.applyGameState)
  const applyDealResult = useGameStore((s) => s.applyDealResult)
  const applyGameOver = useGameStore((s) => s.applyGameOver)
  const applyActionError = useGameStore((s) => s.applyActionError)
  const [started, setStarted] = useState(false)

  useEffect(() => {
    const session = loadSession(gameId)
    if (!session) {
      navigate(`/join/${gameId}`, { replace: true })
      return
    }

    connect(gameId, session.playerId, session.sessionToken, (message) => {
      if (isLobbyStateMessage(message)) {
        applyLobbyState(message.data)
      } else if (isGameStateMessage(message)) {
        setStarted(true)
        applyGameState(message.data)
      } else if (isDealResultMessage(message)) {
        applyDealResult(message.data)
      } else if (isGameOverMessage(message)) {
        applyGameOver(message.data.winner_team)
      } else if (isActionErrorMessage(message)) {
        applyActionError(message.data.reason)
      }
    })

    return () => disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId])

  return started ? <GamePage /> : <LobbyPage />
}
