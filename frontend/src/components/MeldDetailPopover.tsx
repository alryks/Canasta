import { motion } from 'framer-motion'
import { cardLabel, isWildRank } from '../lib/cards'
import type { Meld } from '../lib/protocol'
import { useDragStore } from '../stores/dragStore'
import { PlayingCard } from './PlayingCard'

const SLOT_TRANSITION = { type: 'spring', stiffness: 500, damping: 32 } as const

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
  const hoveredZone = useDragStore((s) => (s.origin === 'hand' ? s.hoveredZone : null))

  return (
    <ul aria-label={`meld-detail-${meld.id}`} className="meld-detail-popover">
      {meld.slots.map((card, i) => (
        <li key={i}>
          <motion.span
            layout
            layoutId={`meld-slot-${meld.id}-${i}`}
            transition={SLOT_TRANSITION}
            style={{ display: 'inline-block' }}
          >
            {card === null ? (
              <PlayingCard size="small" empty />
            ) : canStealFrom && isWildRank(card.rank) ? (
              <PlayingCard
                card={card}
                size="small"
                wild
                pressed={isStealTarget(card.id)}
                selected={
                  isStealTarget(card.id) || hoveredZone === `wild:${meld.id}:${card.id}`
                }
                onClick={() => onSelectStealTarget(card.id)}
                dropZone={`wild:${meld.id}:${card.id}`}
                ariaLabel={cardLabel(card)}
              />
            ) : (
              <PlayingCard card={card} size="small" ariaLabel={cardLabel(card)} />
            )}
          </motion.span>
        </li>
      ))}
    </ul>
  )
}
