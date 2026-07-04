import { motion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'
import { ChatPanel } from '../components/ChatPanel'
import { DealResultModal } from '../components/DealResultModal'
import { DragLayer } from '../components/DragLayer'
import { ErrorToast } from '../components/ErrorToast'
import { EventLog } from '../components/EventLog'
import { GameActionPanel } from '../components/GameActionPanel'
import { GameHeader } from '../components/GameHeader'
import { GameOverModal } from '../components/GameOverModal'
import { Hand } from '../components/Hand'
import { PlayingCard } from '../components/PlayingCard'
import { TeamZone } from '../components/TeamZone'
import { ThresholdIndicator } from '../components/ThresholdIndicator'
import { TurnBanner } from '../components/TurnBanner'
import type { WildSide } from '../components/WildSideChooser'
import { WildSideChooser } from '../components/WildSideChooser'
import {
  compareForHand,
  isWildRank,
  parseSequenceAnchor,
  SEQUENCE_RANKS,
} from '../lib/cards'
import { makeCardDragSource } from '../lib/cardDrag'
import { CARD_ENTER_TO, CARD_FLIGHT_TRANSITION, cardLayoutId } from '../lib/cardMotion'
import { isOpeningThresholdRollback } from '../lib/errors'
import { buildGameUiModel } from '../lib/gameUiModel'
import type { Card, LobbyPlayer, Meld } from '../lib/protocol'
import { createWildPlacementOptions } from '../lib/wildPlacement'
import { useChatStore } from '../stores/chatStore'
import { useConnectionStore } from '../stores/connectionStore'
import type { DragOrigin } from '../stores/dragStore'
import { useDragStore } from '../stores/dragStore'
import { useEventLogStore } from '../stores/eventLogStore'
import { useGameFeedbackStore } from '../stores/gameFeedbackStore'
import { useGameStore } from '../stores/gameStore'
import { orderedHand, reorderHand, syncHandOrder, useHandOrderStore } from '../stores/handOrderStore'
import { useLobbyStore } from '../stores/lobbyStore'

interface StealTarget {
  meldId: string
  wildCardId: string
}

interface PendingWildAdd {
  meldId: string
  cardIds: string[]
}

const TURN_TIMEOUT_SECONDS = 90

function seatTag(
  player: LobbyPlayer | undefined,
  count: number | undefined,
  isTurn: boolean,
  isRecentActor: boolean,
) {
  if (!player) return null
  const classes = [
    'seat-name-tag',
    isTurn ? 'is-turn' : '',
    isRecentActor ? 'is-recent-actor' : '',
    !player.connected ? 'is-offline' : '',
  ]
    .filter(Boolean)
    .join(' ')
  const name = player.is_bot ? player.name : player.name
  const visibleBacks = Math.max(1, Math.min(5, Math.ceil((count ?? 0) / 4)))
  return (
    <div className="seat-player">
      <span className={classes}>
        <span className="seat-name">{name}</span>
        <span className="seat-card-count">{count ?? 0} карт</span>
      </span>
      <span className="opponent-hand-fan" aria-hidden>
        {Array.from({ length: visibleBacks }, (_, index) => (
          <PlayingCard key={index} faceDown size="small" />
        ))}
      </span>
    </div>
  )
}

function wildSideOptions(meld: Meld): { low: boolean; high: boolean } {
  if (meld.kind !== 'SEQUENCE') return { low: false, high: false }
  const anchor = parseSequenceAnchor(meld.rank_or_suit_anchor)
  if (!anchor) return { low: false, high: false }
  return {
    low: anchor.startIndex > 0,
    high: anchor.startIndex + meld.slots.length < SEQUENCE_RANKS.length,
  }
}

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
  const latestFeedbackEvent = useGameFeedbackStore((s) => s.latestEvent)
  const newCardIds = useGameFeedbackStore((s) => s.newCardIds)
  const recentActorId = useGameFeedbackStore((s) => s.recentActorId)
  const recentTeamId = useGameFeedbackStore((s) => s.recentTeamId)
  const recentDiscardCardId = useGameFeedbackStore((s) => s.recentDiscardCardId)
  const clearNewCardIds = useGameFeedbackStore((s) => s.clearNewCardIds)
  const clearLatestFeedbackEvent = useGameFeedbackStore((s) => s.clearLatestEvent)

  const [selectedCardIds, setSelectedCardIds] = useState<string[]>([])
  const [stealTarget, setStealTarget] = useState<StealTarget | null>(null)
  const [pendingWildAdd, setPendingWildAdd] = useState<PendingWildAdd | null>(null)
  const [createWildSide, setCreateWildSide] = useState<WildSide>('low')
  const [offlineCountdown, setOfflineCountdown] = useState<number | null>(null)
  const isDiscardDropTarget = useDragStore(
    (s) => s.hoveredZone === 'discard' && s.origin === 'hand',
  )

  const handOrder = useHandOrderStore((s) => s.order)
  const setHandOrder = useHandOrderStore((s) => s.setOrder)
  const autoSort = useHandOrderStore((s) => s.autoSort)
  const toggleAutoSort = useHandOrderStore((s) => s.toggleAutoSort)

  const turnPlayerId = gameState?.turn_player_id ?? null
  const turnPlayer = players.find((p) => p.id === turnPlayerId)
  const turnPlayerOffline = turnPlayer !== undefined && !turnPlayer.connected
  const hasConnectionBanner = connectionStatus !== 'open'

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

  useEffect(() => {
    if (newCardIds.length === 0) return
    const id = window.setTimeout(clearNewCardIds, 2600)
    return () => window.clearTimeout(id)
  }, [clearNewCardIds, newCardIds])

  useEffect(() => {
    if (!latestFeedbackEvent) return
    const id = window.setTimeout(
      () => clearLatestFeedbackEvent(latestFeedbackEvent.id),
      3600,
    )
    return () => window.clearTimeout(id)
  }, [clearLatestFeedbackEvent, latestFeedbackEvent])

  const myHandRaw = gameState && playerId ? gameState.hands[playerId] : undefined
  const myHand: Card[] = Array.isArray(myHandRaw) ? myHandRaw : []

  const syncedHandOrder = useMemo(
    () => syncHandOrder(myHand, handOrder, compareForHand, autoSort),
    [myHand, handOrder, autoSort],
  )

  useEffect(() => {
    if (syncedHandOrder.join(',') !== handOrder.join(',')) {
      setHandOrder(syncedHandOrder)
    }
  }, [syncedHandOrder, handOrder, setHandOrder])

  const myHandOrdered = useMemo(
    () => orderedHand(myHand, syncedHandOrder),
    [myHand, syncedHandOrder],
  )

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
  const cardsById = new Map(myHand.map((c) => [c.id, c]))
  const handCounts: Record<string, number> = {}
  for (const [pid, hand] of Object.entries(gameState.hands)) {
    if (!Array.isArray(hand)) handCounts[pid] = hand
  }

  const bySeat = new Map(
    players.filter((p) => p.seat !== null).map((p) => [p.seat as number, p]),
  )
  const mySeat = me?.seat ?? null
  const partner = mySeat !== null ? bySeat.get((mySeat + 2) % 4) : undefined
  const leftPlayer = mySeat !== null ? bySeat.get((mySeat + 1) % 4) : undefined
  const rightPlayer = mySeat !== null ? bySeat.get((mySeat + 3) % 4) : undefined

  const gameOver = winnerTeamId !== null
  const isMyTurn = !gameOver && playerId !== null && playerId === gameState.turn_player_id
  const phase = gameState.turn_phase
  const isRollbackError = isOpeningThresholdRollback(lastActionError)
  const viewerTeamOpened =
    viewerTeamId !== null && (gameState.team_opened[viewerTeamId] ?? false)

  const ui = buildGameUiModel({
    gameState,
    isMyTurn,
    gameOver,
    viewerTeamId,
    selectedCardCount: selectedCardIds.length,
    hasStealTarget: stealTarget !== null,
  })

  const topDiscardCard = gameState.discard_pile[gameState.discard_pile.length - 1]
  const draggableCards = [...myHand, ...gameState.discard_pile]
  const ownMelds = viewerTeamId !== null ? (gameState.melds[viewerTeamId] ?? []) : []
  const pendingWildMeld =
    pendingWildAdd !== null
      ? (ownMelds.find((m) => m.id === pendingWildAdd.meldId) ?? null)
      : null

  const selectedCards = selectedCardIds
    .map((id) => cardsById.get(id))
    .filter((c): c is Card => c !== undefined)
  const createWildPlacement = createWildPlacementOptions(selectedCards)
  const createNeedsWildSide = createWildPlacement !== null

  function requestAddToMeld(meldId: string, cardIds: string[]) {
    const meld = ownMelds.find((m) => m.id === meldId)
    const hasWild = cardIds.some((id) => {
      const card = cardsById.get(id)
      return card !== undefined && isWildRank(card.rank)
    })
    if (meld && hasWild) {
      const sides = wildSideOptions(meld)
      if (sides.low && sides.high) {
        setPendingWildAdd({ meldId, cardIds })
        return
      }
      send('add_to_meld', {
        meld_id: meldId,
        card_ids: cardIds,
        wild_side: sides.high ? 'high' : 'low',
      })
      return
    }
    send('add_to_meld', { meld_id: meldId, card_ids: cardIds, wild_side: 'low' })
  }

  function handleCardDrop(zone: string, cardId: string, origin: DragOrigin) {
    if (origin === 'hand') {
      if (zone.startsWith('handslot:')) {
        const targetId = zone.slice('handslot:'.length)
        if (!autoSort && cardId !== targetId) {
          setHandOrder(reorderHand(syncedHandOrder, cardId, targetId))
        }
        return
      }
      if (zone === 'hand') return
      if (!ui.dragActEnabled) return
      if (zone === 'discard') {
        if (!ui.canDiscard) return
        send('discard', { card_id: cardId })
      } else if (zone.startsWith('meld:')) {
        requestAddToMeld(zone.slice('meld:'.length), [cardId])
      } else if (zone.startsWith('wild:')) {
        const [, meldId, wildCardId] = zone.split(':')
        send('steal_wild', {
          meld_id: meldId,
          wild_card_id: wildCardId,
          replacement_card_id: cardId,
        })
      }
    } else if (origin === 'discard' && zone === 'hand') {
      if (ui.dragDrawEnabled) send('draw_discard', {})
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
    send('create_meld', {
      card_ids: selectedCardIds,
      wild_side: createNeedsWildSide ? createWildSide : 'low',
    })
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

      <div className="game-chrome">
        <GameHeader scores={gameState.scores} targetScore={targetScore} />
        <TurnBanner
          turnPlayerId={gameState.turn_player_id}
          viewerId={playerId}
          turnPhase={phase}
          playerNames={playerNames}
        />
        {viewerTeamId !== null && !viewerTeamOpened && (
          <ThresholdIndicator
            teamId={viewerTeamId}
            accumulated={gameState.turn_accumulator[viewerTeamId]}
            threshold={gameState.thresholds[viewerTeamId]}
          />
        )}
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
          <div className="host-skip-bar">
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => send('skip_turn_with_penalty', {})}
            >
              Пропустить ход {turnPlayer?.name} со штрафом
            </button>
          </div>
        )}
      </div>

      <ErrorToast
        reason={isRollbackError ? null : lastActionError}
        onDismiss={dismissActionError}
        offsetForBanner={hasConnectionBanner}
      />

      {lastDealResult && (
        <DealResultModal
          dealNumber={lastDealResult.dealNumber}
          scoresBreakdown={lastDealResult.scoresBreakdown}
          teamScoresAfter={lastDealResult.teamScoresAfter}
          nextDeal={lastDealResult.nextDeal}
          onDismiss={dismissDealResult}
        />
      )}

      {pendingWildMeld !== null && pendingWildAdd !== null && (
        <WildSideChooser
          meld={pendingWildMeld}
          onChoose={(side) => {
            send('add_to_meld', {
              meld_id: pendingWildAdd.meldId,
              card_ids: pendingWildAdd.cardIds,
              wild_side: side,
            })
            setPendingWildAdd(null)
          }}
          onCancel={() => setPendingWildAdd(null)}
        />
      )}

      <div className="game-body">
        <div className="game-playfield">
          <div className="table-felt" aria-label="table">
            <div className="seat-slot seat-slot-top">
              {seatTag(
                partner,
                handCounts[partner?.id ?? ''],
                gameState.turn_player_id === partner?.id,
                recentActorId === partner?.id,
              )}
            </div>

            {Object.entries(gameState.melds)
              .filter(([teamId]) => teamId !== viewerTeamId)
              .map(([teamId, melds]) => (
                <TeamZone
                  key={teamId}
                  teamId={teamId}
                  melds={melds}
                  isOwnTeam={false}
                  canDragAdd={false}
                  canStealFrom={isMyTurn && phase === 'ACT'}
                  stealTarget={stealTarget}
                  highlightedTeamId={recentTeamId}
                  highlightedCardIds={latestFeedbackEvent?.cardIds ?? []}
                  onSelectStealTarget={selectStealTarget}
                />
              ))}

            <div className="seat-slot seat-slot-left">
              {seatTag(
                leftPlayer,
                handCounts[leftPlayer?.id ?? ''],
                gameState.turn_player_id === leftPlayer?.id,
                recentActorId === leftPlayer?.id,
              )}
            </div>

            <div className="seat-slot-center">
              <div
                className={`pile${isMyTurn && phase === 'DRAW' ? ' is-actionable' : ''}${
                  latestFeedbackEvent?.type === 'draw_deck' ? ' is-recent-action' : ''
                }`}
              >
                <span className="pile-label">Колода · {gameState.deck_count}</span>
                {gameState.deck_count > 0 ? (
                  <button
                    type="button"
                    className="deck-pile-btn"
                    aria-label="Взять из колоды"
                    disabled={!ui.canDrawDeck}
                    onClick={() => send('draw_deck', {})}
                  >
                    <span className="deck-stack">
                      <PlayingCard faceDown />
                      {gameState.deck_count > 1 && <PlayingCard faceDown />}
                      {gameState.deck_count > 2 && <PlayingCard faceDown />}
                    </span>
                  </button>
                ) : (
                  <div className="discard-empty" />
                )}
              </div>

              <div
                className={`pile discard-pile${isDiscardDropTarget ? ' is-drop-target' : ''}${
                  ui.canTakeDiscard ? ' is-actionable' : ''
                }${
                  recentDiscardCardId === topDiscardCard?.id ? ' is-recent-action' : ''
                }`}
                data-drop-zone="discard"
              >
                <span className="pile-label">Сброс · {gameState.discard_count}</span>
                {topDiscardCard !== undefined ? (
                  <button
                    type="button"
                    className="discard-pile-btn"
                    disabled={!ui.canTakeDiscard}
                    aria-label="Взять сброс"
                    onClick={() => send('draw_discard', {})}
                  >
                    <motion.span
                      key={topDiscardCard.id}
                      layout
                      layoutId={cardLayoutId(topDiscardCard.id)}
                      initial={{ opacity: 0, y: -24, scale: 0.75 }}
                      animate={CARD_ENTER_TO}
                      transition={CARD_FLIGHT_TRANSITION}
                      style={{ display: 'inline-block' }}
                    >
                      <PlayingCard
                        card={topDiscardCard}
                        onPointerDown={
                          makeCardDragSource(
                            topDiscardCard.id,
                            'discard',
                            ui.dragDrawEnabled,
                            handleCardDrop,
                          ).onPointerDown
                        }
                      />
                    </motion.span>
                  </button>
                ) : (
                  <div className="discard-empty" />
                )}
              </div>
            </div>

            <div className="seat-slot seat-slot-right">
              {seatTag(
                rightPlayer,
                handCounts[rightPlayer?.id ?? ''],
                gameState.turn_player_id === rightPlayer?.id,
                recentActorId === rightPlayer?.id,
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
                  canDragAdd={ui.dragActEnabled}
                  canStealFrom={false}
                  stealTarget={stealTarget}
                  highlightedTeamId={recentTeamId}
                  highlightedCardIds={latestFeedbackEvent?.cardIds ?? []}
                  onSelectStealTarget={selectStealTarget}
                />
              ))}
          </div>
        </div>

        <aside className="game-side-tools" aria-label="side-tools">
          <EventLog entries={logEntries} />
          <ChatPanel
            messages={chatMessages}
            unreadCount={chatUnread}
            playerNames={playerNames}
            onSend={(text) => send('send_chat', { text })}
            onOpen={markChatRead}
          />
        </aside>
      </div>

      <div className="game-command-dock">
        <GameActionPanel
          visible={isMyTurn && !gameOver}
          phase={phase}
          canCreateMeld={ui.canCreateMeld}
          canStealWild={stealTarget !== null}
          selectedCount={selectedCardIds.length}
          createWildPlacement={createWildPlacement}
          createWildSide={createWildSide}
          onCreateWildSideChange={setCreateWildSide}
          onCreateMeld={handleCreateMeld}
          onStealWild={handleStealWild}
        />

        <Hand
          cards={myHandOrdered}
          selectedIds={selectedCardIds}
          newCardIds={newCardIds}
          isMyTurn={isMyTurn}
          isRecentActor={recentActorId === playerId}
          isRollbackNotice={latestFeedbackEvent?.type === 'rollback' || isRollbackError}
          autoSort={autoSort}
          onToggleAutoSort={toggleAutoSort}
          onToggleCard={toggleCard}
          onCardDrop={(zone, cardId) => handleCardDrop(zone, cardId, 'hand')}
        />
      </div>

      <DragLayer cards={draggableCards} />
    </main>
  )
}
