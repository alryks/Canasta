import { useState } from 'react'
import { GameHeader } from '../components/GameHeader'
import { Hand } from '../components/Hand'
import { cardLabel } from '../lib/cards'
import type { Card } from '../lib/protocol'
import { useConnectionStore } from '../stores/connectionStore'
import { useGameStore } from '../stores/gameStore'
import { useLobbyStore } from '../stores/lobbyStore'

function isWildRank(rank: string): boolean {
  return rank === 'JOKER' || rank === '2'
}

interface StealTarget {
  meldId: string
  wildCardId: string
}

// Click-based stand-in for the eventual drag & drop board (plan phase 9):
// every game action is a button click driven by a hand-card selection,
// wired straight to the WS intents the backend already implements in full
// (phase 4). Visual polish (MeldStack, TeamZone, casino styling) lands in
// steps 24+ -- this step only has to prove a full deal is playable.
export function GamePage() {
  const send = useConnectionStore((s) => s.send)
  const playerId = useConnectionStore((s) => s.playerId)
  const gameState = useGameStore((s) => s.state)
  const lastDealResult = useGameStore((s) => s.lastDealResult)
  const winnerTeamId = useGameStore((s) => s.winnerTeamId)
  const lastActionError = useGameStore((s) => s.lastActionError)
  const dismissActionError = useGameStore((s) => s.dismissActionError)
  const players = useLobbyStore((s) => s.players)
  const targetScore = useLobbyStore((s) => s.settings.targetScore)

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

  const isMyTurn = playerId !== null && playerId === gameState.turn_player_id
  const phase = gameState.turn_phase

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

  if (winnerTeamId !== null) {
    return (
      <main>
        <h1>Игра окончена</h1>
        <p>Победила команда {winnerTeamId}</p>
        <ul aria-label="scores">
          {Object.entries(gameState.scores).map(([teamId, score]) => (
            <li key={teamId}>
              Команда {teamId}: {score}
            </li>
          ))}
        </ul>
      </main>
    )
  }

  return (
    <main>
      <GameHeader
        scores={gameState.scores}
        targetScore={targetScore}
        turnPlayerId={gameState.turn_player_id}
        turnPhase={phase}
        viewerId={playerId}
        playerNames={playerNames}
      />

      {lastActionError && (
        <p role="alert">
          Ошибка: {lastActionError}{' '}
          <button type="button" onClick={dismissActionError}>
            ✕
          </button>
        </p>
      )}

      {lastDealResult && (
        <section aria-label="deal-result">
          <p>Сдача №{lastDealResult.dealNumber} завершена.</p>
          <ul>
            {Object.entries(lastDealResult.teamScoresAfter).map(
              ([teamId, score]) => (
                <li key={teamId}>
                  Команда {teamId}: {score}
                </li>
              ),
            )}
          </ul>
        </section>
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
          <div key={teamId} aria-label={`melds-${teamId}`}>
            <h3>
              Команда {teamId} — накоплено {gameState.turn_accumulator[teamId]}/
              {gameState.thresholds[teamId]}
            </h3>
            <ul>
              {melds.map((meld) => (
                <li key={meld.id}>
                  {meld.kind} {meld.rank_or_suit_anchor}:{' '}
                  {meld.slots.map((card, i) =>
                    card === null ? (
                      <span key={i}> _ </span>
                    ) : teamId !== viewerTeamId &&
                      isWildRank(card.rank) &&
                      isMyTurn &&
                      phase === 'ACT' ? (
                      <button
                        key={card.id}
                        type="button"
                        aria-pressed={stealTarget?.wildCardId === card.id}
                        onClick={() => selectStealTarget(meld.id, card.id)}
                      >
                        {cardLabel(card)}
                      </button>
                    ) : (
                      <span key={card.id}> {cardLabel(card)} </span>
                    ),
                  )}
                  {teamId === viewerTeamId && isMyTurn && phase === 'ACT' && (
                    <button
                      type="button"
                      disabled={selectedCardIds.length === 0}
                      onClick={() => handleAddToMeld(meld.id)}
                    >
                      Добавить сюда
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
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
          <button type="button" onClick={() => send('concede_penalty', {})}>
            Не могу выложить
          </button>
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
    </main>
  )
}
