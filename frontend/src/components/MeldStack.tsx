import { motion } from 'framer-motion'
import { useState } from 'react'
import { canastaStatus, cardLabel } from '../lib/cards'
import type { Card, Meld } from '../lib/protocol'
import { useDragStore } from '../stores/dragStore'
import { MeldDetailPopover } from './MeldDetailPopover'
import { PlayingCard } from './PlayingCard'

interface MeldStackProps {
  meld: Meld
  isOwnTeam: boolean
  canAddCards: boolean
  onAddToMeld: () => void
  canDragAdd?: boolean
  canStealFrom: boolean
  isStealTarget: (cardId: string) => boolean
  onSelectStealTarget: (cardId: string) => void
}

// Top card + count, colored by canasta status; click expands
// MeldDetailPopover to see every slot (needed to steal a wild card). Own-team
// melds double as a drop zone for a single dragged hand card (add_to_meld).
export function MeldStack({
  meld,
  isOwnTeam,
  canAddCards,
  onAddToMeld,
  canDragAdd = false,
  canStealFrom,
  isStealTarget,
  onSelectStealTarget,
}: MeldStackProps) {
  const [expanded, setExpanded] = useState(false)
  const dropZoneId = `meld:${meld.id}`
  const isDropTarget = useDragStore((s) => s.hoveredZone === dropZoneId)
  const cards = meld.slots.filter((c): c is Card => c !== null)
  const topCard = cards[cards.length - 1]
  const status = canastaStatus(meld)

  return (
    <div
      className={`meld-stack status-${status}${isDropTarget ? ' is-drop-target' : ''}`}
      data-drop-zone={isOwnTeam && canDragAdd ? dropZoneId : undefined}
    >
      <button
        type="button"
        className="meld-stack-summary"
        aria-expanded={expanded}
        onClick={() => setExpanded((v) => !v)}
      >
        <motion.span
          layout
          layoutId={`meld-top-${meld.id}`}
          transition={{ type: 'spring', stiffness: 500, damping: 32 }}
          style={{ display: 'inline-block' }}
        >
          <PlayingCard card={topCard} size="small" />
        </motion.span>
        <span className="meld-count-badge">×{cards.length}</span>
        <span className="visually-hidden">
          {meld.kind} {meld.rank_or_suit_anchor} — {topCard ? cardLabel(topCard) : '—'} ×
          {cards.length}
        </span>
      </button>

      {expanded && (
        <MeldDetailPopover
          meld={meld}
          canStealFrom={canStealFrom}
          isStealTarget={isStealTarget}
          onSelectStealTarget={onSelectStealTarget}
        />
      )}

      {isOwnTeam && canAddCards && (
        <button type="button" className="btn btn-ghost meld-add-btn" onClick={onAddToMeld}>
          Добавить сюда
        </button>
      )}
    </div>
  )
}
