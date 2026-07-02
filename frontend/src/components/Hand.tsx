import { cardLabel } from '../lib/cards'
import { makeCardDragSource } from '../lib/cardDrag'
import type { Card } from '../lib/protocol'
import { useDragStore } from '../stores/dragStore'
import { PlayingCard } from './PlayingCard'

interface HandProps {
  cards: Card[]
  selectedIds: string[]
  onToggleCard: (cardId: string) => void
  dragEnabled?: boolean
  onCardDrop?: (zone: string, cardId: string) => void
}

// Cards double as click-to-select (still needed for multi-card create_meld,
// see GamePage) and as drag sources (plan section 13) for the single-card
// actions -- discard, add-to-meld, steal-wild -- which map naturally onto a
// drop target. A short movement threshold in makeCardDragSource keeps both
// gestures working on the same element without conflict.
export function Hand({
  cards,
  selectedIds,
  onToggleCard,
  dragEnabled = false,
  onCardDrop,
}: HandProps) {
  const isHandDropTarget = useDragStore((s) => s.hoveredZone === 'hand' && s.origin === 'discard')

  return (
    <ul
      aria-label="hand"
      className={`hand-tray${isHandDropTarget ? ' is-drop-target' : ''}`}
      data-drop-zone="hand"
    >
      {cards.map((card) => {
        const { onPointerDown } = makeCardDragSource(card.id, 'hand', dragEnabled, (zone, id) =>
          onCardDrop?.(zone, id),
        )
        return (
          <li key={card.id}>
            <PlayingCard
              card={card}
              selected={selectedIds.includes(card.id)}
              pressed={selectedIds.includes(card.id)}
              onClick={() => onToggleCard(card.id)}
              onPointerDown={onPointerDown}
              ariaLabel={cardLabel(card)}
            />
          </li>
        )
      })}
    </ul>
  )
}
