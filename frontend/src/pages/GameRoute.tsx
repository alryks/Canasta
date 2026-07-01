import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  isActionErrorMessage,
  isChatMessageMessage,
  isDealResultMessage,
  isGameOverMessage,
  isGameStateMessage,
  isLobbyStateMessage,
  isPlayerConnectionMessage,
} from '../lib/protocol'
import { loadSession } from '../lib/session'
import { useChatStore } from '../stores/chatStore'
import { useConnectionStore } from '../stores/connectionStore'
import { useEventLogStore } from '../stores/eventLogStore'
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
  const addChatMessage = useChatStore((s) => s.addMessage)
  const addLogEntry = useEventLogStore((s) => s.addEntry)
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
        addLogEntry(`Сдача №${message.data.deal_number} завершена`)
      } else if (isGameOverMessage(message)) {
        applyGameOver(message.data.winner_team)
        addLogEntry(`Игра окончена — победила команда ${message.data.winner_team}`)
      } else if (isActionErrorMessage(message)) {
        applyActionError(message.data.reason)
        addLogEntry(`Ошибка: ${message.data.reason}`)
      } else if (isChatMessageMessage(message)) {
        addChatMessage(message.data)
      } else if (isPlayerConnectionMessage(message)) {
        const player = useLobbyStore
          .getState()
          .players.find((p) => p.id === message.data.player_id)
        const name = player?.name ?? message.data.player_id
        addLogEntry(`${name} ${message.data.connected ? 'подключился' : 'отключился'}`)
      }
    })

    return () => disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId])

  return started ? <GamePage /> : <LobbyPage />
}
