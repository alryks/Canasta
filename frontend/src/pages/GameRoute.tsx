import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getLobby } from '../lib/api'
import {
  isActionErrorMessage,
  isChatMessageMessage,
  isDealResultMessage,
  isGameOverMessage,
  isGameStateMessage,
  isLobbyStateMessage,
  isPlayerConnectionMessage,
  isTurnTimerExpiredMessage,
} from '../lib/protocol'
import { isOpeningThresholdRollback, translateActionError } from '../lib/errors'
import { loadSession } from '../lib/session'
import { diffGameStates } from '../lib/gameStateDiff'
import { useChatStore } from '../stores/chatStore'
import { useConnectionStore } from '../stores/connectionStore'
import { useEventLogStore } from '../stores/eventLogStore'
import { useGameFeedbackStore } from '../stores/gameFeedbackStore'
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
  const applyTurnTimerExpired = useGameStore((s) => s.applyTurnTimerExpired)
  const clearTimedOutPlayer = useGameStore((s) => s.clearTimedOutPlayer)
  const setPlayerConnected = useLobbyStore((s) => s.setPlayerConnected)
  const addChatMessage = useChatStore((s) => s.addMessage)
  const addLogEntry = useEventLogStore((s) => s.addEntry)
  const publishFeedback = useGameFeedbackStore((s) => s.publish)
  const [started, setStarted] = useState(false)

  useEffect(() => {
    const session = loadSession(gameId)
    if (!session) {
      navigate(`/join/${gameId}`, { replace: true })
      return
    }

    // The WS socket only sends `lobby_state` while the game is still in the
    // LOBBY status -- reconnecting into an already-started game gets just a
    // `game_state` snapshot (router.py's game_ws), so the roster (names,
    // seats, teams) would otherwise never arrive on a page refresh. Fetch it
    // once over REST regardless; a lobby_state over WS (if any) simply
    // overwrites it later with live data.
    getLobby(gameId)
      .then((lobby) =>
        applyLobbyState({
          players: lobby.players,
          host_id: lobby.host_id,
          settings: {
            target_score: lobby.target_score,
            discard_visibility: lobby.discard_visibility,
          },
        }),
      )
      .catch(() => {})

    connect(gameId, session.playerId, session.sessionToken, (message) => {
      if (isLobbyStateMessage(message)) {
        applyLobbyState(message.data)
      } else if (isGameStateMessage(message)) {
        const previousGameState = useGameStore.getState().state
        const playerNames = Object.fromEntries(
          useLobbyStore.getState().players.map((p) => [p.id, p.name]),
        )
        const { events, newCardIds } = diffGameStates(previousGameState, message.data, {
          viewerId: session.playerId,
          playerNames,
        })
        for (const event of events) addLogEntry(event.text)
        publishFeedback(events.find((event) => event.type !== 'turn') ?? events.at(-1) ?? null, newCardIds)
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
        if (isOpeningThresholdRollback(message.data.reason)) {
          const text = translateActionError(message.data.reason)
          addLogEntry(text)
          publishFeedback(
            {
              type: 'rollback',
              actorId: session.playerId,
              text: 'Порог открытия не набран — карты вернулись в руку',
            },
            [],
          )
        } else {
          addLogEntry(`Ошибка: ${message.data.reason}`)
        }
      } else if (isChatMessageMessage(message)) {
        addChatMessage(message.data)
      } else if (isPlayerConnectionMessage(message)) {
        const player = useLobbyStore
          .getState()
          .players.find((p) => p.id === message.data.player_id)
        const name = player?.name ?? message.data.player_id
        addLogEntry(`${name} ${message.data.connected ? 'подключился' : 'отключился'}`)
        setPlayerConnected(message.data.player_id, message.data.connected)
        if (message.data.connected) clearTimedOutPlayer(message.data.player_id)
      } else if (isTurnTimerExpiredMessage(message)) {
        applyTurnTimerExpired(message.data.player_id)
      }
    })

    return () => disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId])

  return started ? <GamePage /> : <LobbyPage />
}
