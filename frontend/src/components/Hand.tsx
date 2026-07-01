import { cardLabel } from '../lib/cards'
import type { Card } from '../lib/protocol'

interface HandProps {
  cards: Card[]
  selectedIds: string[]
  onToggleCard: (cardId: string) => void
}

// Click-based selection stands in for drag & drop until phase 9 -- clicking a
// card toggles it into the selection used by whichever action button (create
// meld / add to meld / discard) the player clicks next.
export function Hand({ cards, selectedIds, onToggleCard }: HandProps) {
  return (
    <ul aria-label="hand">
      {cards.map((card) => (
        <li key={card.id}>
          <button
            type="button"
            aria-pressed={selectedIds.includes(card.id)}
            onClick={() => onToggleCard(card.id)}
          >
            {cardLabel(card)}
          </button>
        </li>
      ))}
    </ul>
  )
}
