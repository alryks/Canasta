import { useState } from 'react'
import { ChatPanel } from '../components/ChatPanel'
import { ConcedeButton } from '../components/ConcedeButton'
import { DealResultModal } from '../components/DealResultModal'
import { EventLog } from '../components/EventLog'
import { GameHeader } from '../components/GameHeader'
import { GameOverModal } from '../components/GameOverModal'
import { Hand } from '../components/Hand'
import { TeamZone } from '../components/TeamZone'
import { ThresholdIndicator } from '../components/ThresholdIndicator'
import { TurnBanner } from '../components/TurnBanner'
import { cardLabel } from '../lib/cards'
import type { Card } from '../lib/protocol'
import { useChatStore } from '../stores/chatStore'
import { useConnectionStore } from '../stores/connectionStore'
import { useEventLogStore } from '../stores/eventLogStore'
import { useGameStore } from '../stores/gameStore'
import { useLobbyStore } from '../stores/lobbyStore'

interface StealTarget {
  meldId: string
  wildCardId: string
}

// Click-based stand-in for the eventual drag & drop board (plan phase 9):
// every game action is a button click driven by a hand-card selection,
// wired straight to the WS intents the backend already implements in full
// (phase 4). Casino styling (design tokens, card faces) lands in phase 8.
export function GamePage() {
  const send = useConnectionStore((s) => s.send)
  const playerId = useConnectionStore((s) => s.playerId)
  const gameState = useGameStore((s) => s.state)
  const lastDealResult = useGameStore((s) => s.lastDealResult)
  const winnerTeamId = useGameStore((s) => s.winnerTeamId)
  const lastActionError = useGameStore((s) => s.lastActionError)
  const dismissActionError = useGameStore((s) => s.dismissActionError)
  const dismissDealResult = useGameStore((s) => s.dismissDealResult)
  const players = useLobbyStore((s) => s.players)
  const targetScore = useLobbyStore((s) => s.settings.targetScore)
  const chatMessages = useChatStore((s) => s.messages)
  const chatUnread = useChatStore((s) => s.unread)
  const markChatRead = useChatStore((s) => s.markRead)
  const logEntries = useEventLogStore((s) => s.entries)

  const [selectedCardIds, setSelectedCardIds] = useState<string[]>([])
  const [stealTarget, setStealTarget] = useState<StealTarget | null>(null)

  if (gameState === null) {
    return (
      <main>
        <p>Загрузка партии…</p>
      </main>
    )
  }

  const playerNames = Object.fromEntries(players.map((p) => [p.id, p.name]))
  const viewerTeamId =
    players.find((p) => p.id === playerId)?.team_id ?? null
  const myHandRaw = playerId ? gameState.hands[playerId] : undefined
  const myHand: Card[] = Array.isArray(myHandRaw) ? myHandRaw : []
  const opponentCounts = Object.entries(gameState.hands).filter(
    ([pid, hand]) => pid !== playerId && !Array.isArray(hand),
  ) as [string, number][]

  const gameOver = winnerTeamId !== null
  const isMyTurn =
    !gameOver && playerId !== null && playerId === gameState.turn_player_id
  const phase = gameState.turn_phase
  const viewerTeamOpened =
    viewerTeamId !== null &&
    gameState.turn_accumulator[viewerTeamId] >= gameState.thresholds[viewerTeamId]

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
    <main>
      {gameOver && winnerTeamId !== null && (
        <GameOverModal
          winnerTeamId={winnerTeamId}
          finalScores={lastDealResult?.teamScoresAfter ?? gameState.scores}
        />
      )}

      <GameHeader scores={gameState.scores} targetScore={targetScore} />
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
        <p role="alert">
          Ошибка: {lastActionError}{' '}
          <button type="button" onClick={dismissActionError}>
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

      <section aria-label="table">
        <p>Колода: {gameState.deck_count} карт</p>
        <p>
          Сброс:{' '}
          {gameState.discard_pile.length > 0
            ? gameState.discard_pile.map(cardLabel).join(', ')
            : 'пусто'}
        </p>

        {isMyTurn && phase === 'DRAW' && (
          <>
            <button type="button" onClick={() => send('draw_deck', {})}>
              Взять из колоды
            </button>
            <button
              type="button"
              disabled={gameState.discard_pile.length === 0}
              onClick={() => send('draw_discard', {})}
            >
              Взять из сброса
            </button>
          </>
        )}

        {Object.entries(gameState.melds).map(([teamId, melds]) => (
          <TeamZone
            key={teamId}
            teamId={teamId}
            melds={melds}
            isOwnTeam={teamId === viewerTeamId}
            canAddCards={
              teamId === viewerTeamId &&
              isMyTurn &&
              phase === 'ACT' &&
              selectedCardIds.length > 0
            }
            onAddToMeld={handleAddToMeld}
            canStealFrom={teamId !== viewerTeamId && isMyTurn && phase === 'ACT'}
            stealTarget={stealTarget}
            onSelectStealTarget={selectStealTarget}
          />
        ))}
      </section>

      <section aria-label="opponents">
        {opponentCounts.map(([pid, count]) => (
          <p key={pid}>
            {playerNames[pid] ?? pid}: {count} карт
          </p>
        ))}
      </section>

      <Hand cards={myHand} selectedIds={selectedCardIds} onToggleCard={toggleCard} />

      {isMyTurn && phase === 'ACT' && (
        <div aria-label="actions">
          <button
            type="button"
            disabled={selectedCardIds.length === 0}
            onClick={handleCreateMeld}
          >
            Выложить новый мелд
          </button>
          <button
            type="button"
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
