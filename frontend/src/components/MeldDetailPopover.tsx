import { cardLabel, isWildRank } from '../lib/cards'
import type { Meld } from '../lib/protocol'

interface MeldDetailPopoverProps {
  meld: Meld
  canStealFrom: boolean
  isStealTarget: (cardId: string) => boolean
  onSelectStealTarget: (cardId: string) => void
}

// Shows every positional slot (including empty ones) -- needed to see which
// slot a wild card is standing in for, since stealing requires swapping it
// for the matching natural card (plan section 5, UC-3).
export function MeldDetailPopover({
  meld,
  canStealFrom,
  isStealTarget,
  onSelectStealTarget,
}: MeldDetailPopoverProps) {
  return (
    <ul aria-label={`meld-detail-${meld.id}`}>
      {meld.slots.map((card, i) =>
        card === null ? (
          <li key={i}>—</li>
        ) : (
          <li key={card.id}>
            {canStealFrom && isWildRank(card.rank) ? (
              <button
                type="button"
                aria-pressed={isStealTarget(card.id)}
                onClick={() => onSelectStealTarget(card.id)}
              >
                {cardLabel(card)}
              </button>
            ) : (
              cardLabel(card)
            )}
          </li>
        ),
      )}
    </ul>
  )
}
