import { useState } from 'react'
import type { CSSProperties } from 'react'
import {
  canastaStatus,
  cardLabel,
  isWildRank,
  parseSequenceAnchor,
  SEQUENCE_RANKS,
  suitSymbol,
} from '../lib/cards'
import { meldCardOverlapPx } from '../lib/meldLayout'
import type { Card, Meld } from '../lib/protocol'
import { useDragStore } from '../stores/dragStore'
import { PlayingCard } from './PlayingCard'

interface MeldStackProps {
  meld: Meld
  isOwnTeam: boolean
  canDragAdd?: boolean
  canStealFrom: boolean
  highlightedCardIds?: string[]
  isRecentAction?: boolean
  isStealTarget: (cardId: string) => boolean
  onSelectStealTarget: (cardId: string) => void
}

const STATUS_LABELS: Record<string, string> = {
  clean: 'Чистая канаста',
  dirty: 'Грязная канаста',
  wild: 'Козырная канаста',
}

function meldCaption(meld: Meld, cards: Card[]): string {
  if (meld.kind === 'SET') return `${meld.rank_or_suit_anchor} ×${cards.length}`
  if (meld.kind === 'SEQUENCE') {
    const anchor = parseSequenceAnchor(meld.rank_or_suit_anchor)
    if (anchor) {
      const from = SEQUENCE_RANKS[anchor.startIndex]
      const to = SEQUENCE_RANKS[anchor.startIndex + cards.length - 1]
      return `${suitSymbol(anchor.suit)} ${from}–${to}`
    }
  }
  return `Козыри ×${cards.length}`
}

// Every card of an in-progress meld is laid out in an overlapping strip, so
// it's always visible which rank each wild card is standing in for (the user
// picks a side when adding one). Own-team melds are drop zones for
// add_to_meld; opponents' wild cards are themselves steal_wild drop/click
// targets.
//
// A completed canasta collapses into a tight face-down pile so a table full
// of canastas doesn't shrink everything else (FR follow-up). It expands on
// click. Drag-to-steal targets the collapsed pile when it has a single wild;
// otherwise expand the pile first to pick the wild card.
export function MeldStack({
  meld,
  isOwnTeam,
  canDragAdd = false,
  canStealFrom,
  highlightedCardIds = [],
  isRecentAction = false,
  isStealTarget,
  onSelectStealTarget,
}: MeldStackProps) {
  const [manuallyExpanded, setManuallyExpanded] = useState(false)
  const dropZoneId = `meld:${meld.id}`
  const hoveredZone = useDragStore((s) => (s.origin === 'hand' ? s.hoveredZone : null))
  const isDropTarget = hoveredZone === dropZoneId
  const cards = meld.slots.filter((c): c is Card => c !== null)
  const highlightedCards = new Set(highlightedCardIds)
  const status = canastaStatus(meld)
  const meldOverlap = meldCardOverlapPx(cards.length)

  const isClosedCanasta = status !== 'open'
  const stealableWilds = cards.filter(
    (c) => canStealFrom && meld.kind !== 'WILD_CANASTA' && isWildRank(c.rank),
  )
  const collapsedStealZone =
    stealableWilds.length === 1 ? `wild:${meld.id}:${stealableWilds[0].id}` : null
  const isCollapsedStealTarget = collapsedStealZone !== null && hoveredZone === collapsedStealZone
  const collapsed = isClosedCanasta && !manuallyExpanded

  if (collapsed) {
    const topCard = cards[cards.length - 1]
    return (
      <div
        aria-label={`meld-${meld.id}`}
        className={`meld-stack is-collapsed status-${status}${
          isCollapsedStealTarget ? ' is-drop-target' : ''
        }${isRecentAction ? ' is-recent-action' : ''}${
          isRecentAction && isClosedCanasta ? ' is-new-canasta' : ''
        }`}
      >
        <button
          type="button"
          className="canasta-pile-btn"
          onClick={() => setManuallyExpanded(true)}
          data-drop-zone={collapsedStealZone ?? undefined}
          aria-label={`${STATUS_LABELS[status]} ${meldCaption(meld, cards)} — показать карты`}
          title="Показать карты канасты"
        >
          <span className="canasta-pile">
            <PlayingCard faceDown size="small" />
            <PlayingCard faceDown size="small" />
            <span className="canasta-top-card">
              <PlayingCard
                card={topCard}
                size="small"
                showPoints={false}
                className={highlightedCards.has(topCard.id) ? 'is-new-card' : ''}
                ariaLabel={cardLabel(topCard)}
              />
            </span>
            <span className="canasta-count">×{cards.length}</span>
          </span>
        </button>
        <span className="meld-caption">
          <span className={`meld-status-badge status-${status}`}>{STATUS_LABELS[status]}</span>
        </span>
      </div>
    )
  }

  return (
    <div
      aria-label={`meld-${meld.id}`}
      className={`meld-stack status-${status}${isDropTarget ? ' is-drop-target' : ''}${
        isRecentAction ? ' is-recent-action' : ''
      }`}
      data-drop-zone={isOwnTeam && canDragAdd ? dropZoneId : undefined}
    >
      <ul className="meld-cards" style={{ '--meld-overlap': `${meldOverlap}px` } as CSSProperties}>
        {cards.map((card) => {
          const stealable = canStealFrom && isWildRank(card.rank)
          return (
            <li key={card.id}>
              <span className="meld-card-wrap">
                {stealable ? (
                  <PlayingCard
                    card={card}
                    size="small"
                    wild
                    className={highlightedCards.has(card.id) ? 'is-new-card' : ''}
                    pressed={isStealTarget(card.id)}
                    selected={
                      isStealTarget(card.id) || hoveredZone === `wild:${meld.id}:${card.id}`
                    }
                    onClick={() => onSelectStealTarget(card.id)}
                    dropZone={`wild:${meld.id}:${card.id}`}
                    ariaLabel={cardLabel(card)}
                  />
                ) : (
                  <PlayingCard
                    card={card}
                    size="small"
                    className={highlightedCards.has(card.id) ? 'is-new-card' : ''}
                    ariaLabel={cardLabel(card)}
                  />
                )}
              </span>
            </li>
          )
        })}
      </ul>
      <span className="meld-caption" title={meldCaption(meld, cards)}>
        <span className="meld-caption-text">{meldCaption(meld, cards)}</span>
        {isClosedCanasta && (
          <>
            <span className={`meld-status-badge status-${status}`}>{STATUS_LABELS[status]}</span>
            <button
              type="button"
              className="canasta-collapse-btn"
              onClick={() => setManuallyExpanded(false)}
              aria-label={`Свернуть канасту ${meldCaption(meld, cards)}`}
              title="Свернуть канасту"
            >
              Свернуть
            </button>
          </>
        )}
      </span>
    </div>
  )
}
