import type { CSSProperties } from 'react'
import { cardLabel } from '../lib/cards'
import { makeCardDragSource } from '../lib/cardDrag'
import type { Card } from '../lib/protocol'
import { useDragStore } from '../stores/dragStore'
import { PlayingCard } from './PlayingCard'

interface HandProps {
  cards: Card[]
  selectedIds: string[]
  newCardIds?: string[]
  isMyTurn?: boolean
  isRecentActor?: boolean
  isRollbackNotice?: boolean
  autoSort: boolean
  onToggleAutoSort: () => void
  onToggleCard: (cardId: string) => void
  onCardDrop: (zone: string, cardId: string) => void
}

function handOverlapRatio(cardCount: number): number {
  if (cardCount <= 1) return 1
  return Math.max(0.32, Math.min(0.58, 7 / cardCount))
}

export function Hand({
  cards,
  selectedIds,
  newCardIds = [],
  isMyTurn = false,
  isRecentActor = false,
  isRollbackNotice = false,
  autoSort,
  onToggleAutoSort,
  onToggleCard,
  onCardDrop,
}: HandProps) {
  const draggingCardId = useDragStore((s) => (s.origin === 'hand' ? s.cardId : null))
  const isHandDropTarget = useDragStore(
    (s) => s.hoveredZone === 'hand' && s.origin === 'discard',
  )
  const reorderTarget = useDragStore((s) =>
    s.origin === 'hand' && s.hoveredZone?.startsWith('handslot:')
      ? s.hoveredZone.slice('handslot:'.length)
      : null,
  )
  const overlap = handOverlapRatio(cards.length)
  const newCardIdSet = new Set(newCardIds)

  return (
    <section
      className={`hand-dock${isMyTurn ? ' is-my-turn' : ''}${
        isRecentActor ? ' is-recent-actor' : ''
      }${isRollbackNotice ? ' is-rollback-notice' : ''}`}
      aria-label="hand-area"
    >
      <div className="hand-toolbar">
        <span className="hand-count">{cards.length}</span>
        {isRollbackNotice && (
          <span className="hand-rollback-note" role="status">
            Порог не набран — карты вернулись в руку
          </span>
        )}
        <label className="hand-auto-sort">
          <span className="hand-auto-sort-label">Автосортировка</span>
          <button
            type="button"
            role="switch"
            aria-checked={autoSort}
            aria-label="Автосортировка"
            className={`ui-switch${autoSort ? ' is-on' : ''}`}
            onClick={onToggleAutoSort}
          >
            <span className="ui-switch-thumb" aria-hidden />
          </button>
        </label>
      </div>
      <div className="hand-tray-wrap">
        <ul
          aria-label="hand"
          className={`hand-tray${isHandDropTarget ? ' is-drop-target' : ''}`}
          data-drop-zone="hand"
          style={{ '--hand-open-overlap': overlap } as CSSProperties}
        >
          {cards.map((card) => {
            const { onPointerDown } = makeCardDragSource(card.id, 'hand', true, (zone, id) =>
              onCardDrop(zone, id),
            )
            return (
              <li
                key={card.id}
                data-drop-zone={`handslot:${card.id}`}
                className={reorderTarget === card.id ? 'is-insert-target' : ''}
              >
                <PlayingCard
                  card={card}
                  selected={selectedIds.includes(card.id)}
                  pressed={selectedIds.includes(card.id)}
                  dragging={draggingCardId === card.id}
                  className={newCardIdSet.has(card.id) ? 'is-new-card' : ''}
                  onClick={() => onToggleCard(card.id)}
                  onPointerDown={onPointerDown}
                  ariaLabel={cardLabel(card)}
                />
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}
