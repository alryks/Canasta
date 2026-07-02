import { createPortal } from 'react-dom'
import type { Card } from '../lib/protocol'
import { useDragStore } from '../stores/dragStore'
import { PlayingCard } from './PlayingCard'

interface DragLayerProps {
  cards: Card[]
}

// Portal overlay drawing the "ghost" of the card under the pointer while
// dragging (plan section 13) -- the source card dims via is-dragging-source
// instead of disappearing, and this ghost is purely visual (pointer-events
// none) so elementFromPoint hit-testing in useCardDrag sees through it.
export function DragLayer({ cards }: DragLayerProps) {
  const cardId = useDragStore((s) => s.cardId)
  const pointer = useDragStore((s) => s.pointer)

  if (!cardId) return null
  const card = cards.find((c) => c.id === cardId)
  if (!card) return null

  return createPortal(
    <div
      style={{
        position: 'fixed',
        left: pointer.x,
        top: pointer.y,
        transform: 'translate(-50%, -50%) rotate(-4deg)',
        pointerEvents: 'none',
        zIndex: 100,
      }}
    >
      <PlayingCard card={card} selected />
    </div>,
    document.body,
  )
}
