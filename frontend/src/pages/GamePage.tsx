import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { ChatPanel } from '../components/ChatPanel'
import { ConcedeButton } from '../components/ConcedeButton'
import { DealResultModal } from '../components/DealResultModal'
import { DragLayer } from '../components/DragLayer'
import { EventLog } from '../components/EventLog'
import { GameHeader } from '../components/GameHeader'
import { GameOverModal } from '../components/GameOverModal'
import { Hand } from '../components/Hand'
import { PlayingCard } from '../components/PlayingCard'
import { TeamZone } from '../components/TeamZone'
import { ThresholdIndicator } from '../components/ThresholdIndicator'
import { TurnBanner } from '../components/TurnBanner'
import { cardLabel } from '../lib/cards'
import { makeCardDragSource } from '../lib/cardDrag'
import type { Card, LobbyPlayer } from '../lib/protocol'
import { useChatStore } from '../stores/chatStore'
import { useConnectionStore } from '../stores/connectionStore'
import type { DragOrigin } from '../stores/dragStore'
import { useDragStore } from '../stores/dragStore'
import { useEventLogStore } from '../stores/eventLogStore'
import { useGameStore } from '../stores/gameStore'
import { useLobbyStore } from '../stores/lobbyStore'

interface StealTarget {
  meldId: string
  wildCardId: string
}

// Mirrors backend/app/ws/turn_timer.py's TURN_TIMEOUT_SECONDS -- the server
// never sends a start time, so this is a cosmetic, approximate countdown
// (plan section 15); the authoritative signal is the turn_timer_expired
// message that unlocks the host's skip button below.
const TURN_TIMEOUT_SECONDS = 90

// Turn order goes seat 0->1->2->3->0 and teams are seat%2 (router.py
// _team_for_seat), so partner = seat+2, and the other two seats are the
// opponents sitting either side -- this gives the classic "you at the
// bottom, partner across, opponents left/right" table orientation.
function seatTag(player: LobbyPlayer | undefined, count: number | undefined, isTurn: boolean) {
  if (!player) return null
  const classes = [
    'seat-name-tag',
    isTurn ? 'is-turn' : '',
    !player.connected ? 'is-offline' : '',
  ]
    .filter(Boolean)
    .join(' ')
  const name = player.is_bot ? `🤖 ${player.name}` : player.name
  return <span className={classes}>{`${name}: ${count ?? 0} карт`}</span>
}

// Two interaction modes coexist on purpose (plan section 5): dragging a
// hand card onto the discard pile / an own meld / an opponent's wild card
// performs that single-card action directly, while click-to-select plus a
// button remains for create_meld (a new meld usually needs 2-3 cards at
// once, which doesn't reduce to a single drag gesture) and stays as a
// fallback everywhere else -- both paths drive the exact same WS intents.
export function GamePage() {
  const send = useConnectionStore((s) => s.send)
  const playerId = useConnectionStore((s) => s.playerId)
  const connectionStatus = useConnectionStore((s) => s.status)
  const gameState = useGameStore((s) => s.state)
  const lastDealResult = useGameStore((s) => s.lastDealResult)
  const winnerTeamId = useGameStore((s) => s.winnerTeamId)
  const lastActionError = useGameStore((s) => s.lastActionError)
  const dismissActionError = useGameStore((s) => s.dismissActionError)
  const dismissDealResult = useGameStore((s) => s.dismissDealResult)
  const timedOutPlayerId = useGameStore((s) => s.timedOutPlayerId)
  const players = useLobbyStore((s) => s.players)
  const hostId = useLobbyStore((s) => s.hostId)
  const targetScore = useLobbyStore((s) => s.settings.targetScore)
  const chatMessages = useChatStore((s) => s.messages)
  const chatUnread = useChatStore((s) => s.unread)
  const markChatRead = useChatStore((s) => s.markRead)
  const logEntries = useEventLogStore((s) => s.entries)

  const [selectedCardIds, setSelectedCardIds] = useState<string[]>([])
  const [stealTarget, setStealTarget] = useState<StealTarget | null>(null)
  const [offlineCountdown, setOfflineCountdown] = useState<number | null>(null)
  const isDiscardDropTarget = useDragStore(
    (s) => s.hoveredZone === 'discard' && s.origin === 'hand',
  )

  const turnPlayerId = gameState?.turn_player_id ?? null
  const turnPlayer = players.find((p) => p.id === turnPlayerId)
  const turnPlayerOffline = turnPlayer !== undefined && !turnPlayer.connected

  // Cosmetic local countdown (see TURN_TIMEOUT_SECONDS) -- restarts whenever
  // the turn moves to a new (offline) player, and stops once either they
  // reconnect or the server's turn_timer_expired actually arrives.
  useEffect(() => {
    if (!turnPlayerOffline || timedOutPlayerId === turnPlayerId) {
      setOfflineCountdown(null)
      return
    }
    setOfflineCountdown(TURN_TIMEOUT_SECONDS)
    const id = setInterval(() => {
      setOfflineCountdown((c) => (c === null ? null : Math.max(0, c - 1)))
    }, 1000)
    return () => clearInterval(id)
  }, [turnPlayerId, turnPlayerOffline, timedOutPlayerId])

  const connectionBanner =
    connectionStatus === 'open' ? null : (
      <div
        className={`connection-banner${connectionStatus === 'connecting' ? ' is-connecting' : ''}`}
        role="status"
      >
        <span className="spinner" />
        {connectionStatus === 'connecting' || connectionStatus === 'idle'
          ? 'Подключение к партии…'
          : 'Соединение потеряно — обновите страницу, чтобы переподключиться'}
      </div>
    )

  if (gameState === null) {
    return (
      <main className="page-shell">
        {connectionBanner}
        <p>Загрузка партии…</p>
      </main>
    )
  }

  const playerNames = Object.fromEntries(players.map((p) => [p.id, p.name]))
  const me = players.find((p) => p.id === playerId)
  const isHost = playerId !== null && playerId === hostId
  const viewerTeamId = me?.team_id ?? null
  const myHandRaw = playerId ? gameState.hands[playerId] : undefined
  const myHand: Card[] = Array.isArray(myHandRaw) ? myHandRaw : []
  const handCounts: Record<string, number> = {}
  for (const [pid, hand] of Object.entries(gameState.hands)) {
    if (!Array.isArray(hand)) handCounts[pid] = hand
  }

  const bySeat = new Map(
    players.filter((p) => p.seat !== null).map((p) => [p.seat as number, p]),
  )
  const mySeat = me?.seat ?? null
  const partner = mySeat !== null ? bySeat.get((mySeat + 2) % 4) : undefined
  const rightPlayer = mySeat !== null ? bySeat.get((mySeat + 1) % 4) : undefined
  const leftPlayer = mySeat !== null ? bySeat.get((mySeat + 3) % 4) : undefined

  const gameOver = winnerTeamId !== null
  const isMyTurn =
    !gameOver && playerId !== null && playerId === gameState.turn_player_id
  const phase = gameState.turn_phase
  const viewerTeamOpened =
    viewerTeamId !== null &&
    gameState.turn_accumulator[viewerTeamId] >= gameState.thresholds[viewerTeamId]

  const discardFan = gameState.discard_pile.slice(-3)
  const topDiscardCard = gameState.discard_pile[gameState.discard_pile.length - 1]
  const dragActEnabled = isMyTurn && phase === 'ACT'
  const dragDrawEnabled = isMyTurn && phase === 'DRAW' && gameState.discard_pile.length > 0
  const draggableCards = [...myHand, ...gameState.discard_pile]

  function handleCardDrop(zone: string, cardId: string, origin: DragOrigin) {
    if (origin === 'hand') {
      if (zone === 'discard') {
        send('discard', { card_id: cardId })
      } else if (zone.startsWith('meld:')) {
        send('add_to_meld', { meld_id: zone.slice('meld:'.length), card_ids: [cardId] })
      } else if (zone.startsWith('wild:')) {
        const [, meldId, wildCardId] = zone.split(':')
        send('steal_wild', {
          meld_id: meldId,
          wild_card_id: wildCardId,
          replacement_card_id: cardId,
        })
      }
    } else if (origin === 'discard' && zone === 'hand') {
      send('draw_discard', {})
    }
  }

  function toggleCard(cardId: string) {
    setSelectedCardIds((ids) =>
      ids.includes(cardId) ? ids.filter((id) => id !== cardId) : [...ids, cardId],
    )
  }

  function selectStealTarget(meldId: string, wildCardId: string) {
    setStealTarget((current) =>
      current?.meldId === meldId && current.wildCardId === wildCardId
        ? null
        : { meldId, wildCardId },
    )
  }

  function handleCreateMeld() {
    send('create_meld', { card_ids: selectedCardIds })
    setSelectedCardIds([])
  }

  function handleAddToMeld(meldId: string) {
    send('add_to_meld', { meld_id: meldId, card_ids: selectedCardIds })
    setSelectedCardIds([])
  }

  function handleDiscard() {
    send('discard', { card_id: selectedCardIds[0] })
    setSelectedCardIds([])
  }

  function handleStealWild() {
    if (!stealTarget) return
    send('steal_wild', {
      meld_id: stealTarget.meldId,
      wild_card_id: stealTarget.wildCardId,
      replacement_card_id: selectedCardIds[0],
    })
    setSelectedCardIds([])
    setStealTarget(null)
  }

  return (
    <main className="table-frame">
      {connectionBanner}
      {gameOver && winnerTeamId !== null && (
        <GameOverModal
          winnerTeamId={winnerTeamId}
          finalScores={lastDealResult?.teamScoresAfter ?? gameState.scores}
        />
      )}

      <GameHeader scores={gameState.scores} targetScore={targetScore} />

      {!gameOver && turnPlayerOffline && (
        <p className="status-line offline-countdown" role="status">
          {turnPlayer?.name} офлайн.{' '}
          {timedOutPlayerId === turnPlayerId
            ? isHost
              ? 'Можно пропустить ход со штрафом.'
              : 'Хост может пропустить его ход.'
            : `Автопропуск станет доступен хосту через ${offlineCountdown ?? TURN_TIMEOUT_SECONDS}с.`}
        </p>
      )}
      {!gameOver && isHost && timedOutPlayerId === turnPlayerId && (
        <div className="action-bar">
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => send('skip_turn_with_penalty', {})}
          >
            Пропустить ход {turnPlayer?.name} со штрафом
          </button>
        </div>
      )}
      <TurnBanner
        turnPlayerId={gameState.turn_player_id}
        viewerId={playerId}
        turnPhase={phase}
        playerNames={playerNames}
      />
      {viewerTeamId !== null && (
        <ThresholdIndicator
          teamId={viewerTeamId}
          accumulated={gameState.turn_accumulator[viewerTeamId]}
          threshold={gameState.thresholds[viewerTeamId]}
        />
      )}

      {lastActionError && (
        <p role="alert" className="error-text">
          Ошибка: {lastActionError}{' '}
          <button type="button" className="btn btn-icon" onClick={dismissActionError}>
            ✕
          </button>
        </p>
      )}

      {lastDealResult && (
        <DealResultModal
          dealNumber={lastDealResult.dealNumber}
          scoresBreakdown={lastDealResult.scoresBreakdown}
          teamScoresAfter={lastDealResult.teamScoresAfter}
          nextDeal={lastDealResult.nextDeal}
          onDismiss={dismissDealResult}
        />
      )}

      <div className="table-felt" aria-label="table">
        <div className="seat-slot seat-slot-top">
          {seatTag(partner, handCounts[partner?.id ?? ''], gameState.turn_player_id === partner?.id)}
        </div>

        {Object.entries(gameState.melds)
          .filter(([teamId]) => teamId !== viewerTeamId)
          .map(([teamId, melds]) => (
            <TeamZone
              key={teamId}
              teamId={teamId}
              melds={melds}
              isOwnTeam={false}
              canAddCards={false}
              onAddToMeld={handleAddToMeld}
              canStealFrom={isMyTurn && phase === 'ACT'}
              stealTarget={stealTarget}
              onSelectStealTarget={selectStealTarget}
            />
          ))}

        <div className="seat-slot seat-slot-left">
          {seatTag(
            leftPlayer,
            handCounts[leftPlayer?.id ?? ''],
            gameState.turn_player_id === leftPlayer?.id,
          )}
        </div>

        <div className="seat-slot-center">
          <div className="pile">
            <span className="pile-label">Колода</span>
            {gameState.deck_count > 0 ? (
              <div className="deck-stack">
                <PlayingCard faceDown />
                {gameState.deck_count > 1 && <PlayingCard faceDown />}
                {gameState.deck_count > 2 && <PlayingCard faceDown />}
              </div>
            ) : (
              <div className="discard-empty" />
            )}
            <p>Колода: {gameState.deck_count} карт</p>
          </div>

          <div
            className={`pile${isDiscardDropTarget ? ' is-drop-target' : ''}`}
            data-drop-zone="discard"
          >
            <span className="pile-label">Сброс</span>
            {discardFan.length > 0 ? (
              <div className="discard-fan">
                {discardFan.map((card, i) => {
                  const isTop = card.id === topDiscardCard?.id
                  const { onPointerDown } = makeCardDragSource(
                    card.id,
                    'discard',
                    isTop && dragDrawEnabled,
                    handleCardDrop,
                  )
                  return (
                    <motion.span
                      key={i}
                      layout
                      layoutId={isTop ? 'discard-top' : `discard-fan-${i}`}
                      transition={{ type: 'spring', stiffness: 500, damping: 32 }}
                      style={{ display: 'inline-block' }}
                    >
                      <PlayingCard card={card} onPointerDown={isTop ? onPointerDown : undefined} />
                    </motion.span>
                  )
                })}
              </div>
            ) : (
              <div className="discard-empty" />
            )}
            <p>
              Сброс:{' '}
              {gameState.discard_pile.length > 0
                ? gameState.discard_pile.map(cardLabel).join(', ')
                : 'пусто'}
            </p>
          </div>
        </div>

        <div className="seat-slot seat-slot-right">
          {seatTag(
            rightPlayer,
            handCounts[rightPlayer?.id ?? ''],
            gameState.turn_player_id === rightPlayer?.id,
          )}
        </div>

        {Object.entries(gameState.melds)
          .filter(([teamId]) => teamId === viewerTeamId)
          .map(([teamId, melds]) => (
            <TeamZone
              key={teamId}
              teamId={teamId}
              melds={melds}
              isOwnTeam
              canAddCards={isMyTurn && phase === 'ACT' && selectedCardIds.length > 0}
              onAddToMeld={handleAddToMeld}
              canDragAdd={dragActEnabled}
              canStealFrom={false}
              stealTarget={stealTarget}
              onSelectStealTarget={selectStealTarget}
            />
          ))}
      </div>

      {isMyTurn && phase === 'DRAW' && (
        <div className="action-bar">
          <button type="button" className="btn btn-primary" onClick={() => send('draw_deck', {})}>
            Взять из колоды
          </button>
          <button
            type="button"
            className="btn"
            disabled={gameState.discard_pile.length === 0}
            onClick={() => send('draw_discard', {})}
          >
            Взять из сброса
          </button>
        </div>
      )}

      <Hand
        cards={myHand}
        selectedIds={selectedCardIds}
        onToggleCard={toggleCard}
        dragEnabled={dragActEnabled}
        onCardDrop={(zone, cardId) => handleCardDrop(zone, cardId, 'hand')}
      />
      <DragLayer cards={draggableCards} />

      {isMyTurn && phase === 'ACT' && (
        <div className="action-bar" aria-label="actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={selectedCardIds.length === 0}
            onClick={handleCreateMeld}
          >
            Выложить новый мелд
          </button>
          <button
            type="button"
            className="btn"
            disabled={selectedCardIds.length !== 1}
            onClick={handleDiscard}
          >
            Сбросить
          </button>
          <ConcedeButton
            visible={!viewerTeamOpened}
            onConcede={() => send('concede_penalty', {})}
          />
          {stealTarget && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={selectedCardIds.length !== 1}
              onClick={handleStealWild}
            >
              Украсть козырь
            </button>
          )}
        </div>
      )}

      <EventLog entries={logEntries} />
      <ChatPanel
        messages={chatMessages}
        unreadCount={chatUnread}
        playerNames={playerNames}
        onSend={(text) => send('send_chat', { text })}
        onOpen={markChatRead}
      />
    </main>
  )
}
