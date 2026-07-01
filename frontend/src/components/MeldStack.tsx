import { useState } from 'react'
import { canastaStatus, cardLabel } from '../lib/cards'
import type { Card, Meld } from '../lib/protocol'
import { MeldDetailPopover } from './MeldDetailPopover'

const STATUS_BORDER: Record<string, string> = {
  open: '1px dashed #999',
  clean: '2px solid #2e7d32',
  dirty: '2px solid #c62828',
  wild: '2px solid #6a1b9a',
}

interface MeldStackProps {
  meld: Meld
  isOwnTeam: boolean
  canAddCards: boolean
  onAddToMeld: () => void
  canStealFrom: boolean
  isStealTarget: (cardId: string) => boolean
  onSelectStealTarget: (cardId: string) => void
}

// Top card + count, colored by canasta status; click expands
// MeldDetailPopover to see every slot (needed to steal a wild card).
export function MeldStack({
  meld,
  isOwnTeam,
  canAddCards,
  onAddToMeld,
  canStealFrom,
  isStealTarget,
  onSelectStealTarget,
}: MeldStackProps) {
  const [expanded, setExpanded] = useState(false)
  const cards = meld.slots.filter((c): c is Card => c !== null)
  const topCard = cards[cards.length - 1]
  const status = canastaStatus(meld)

  return (
    <div style={{ border: STATUS_BORDER[status] }}>
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((v) => !v)}
      >
        {meld.kind} {meld.rank_or_suit_anchor} — {topCard ? cardLabel(topCard) : '—'} ×
        {cards.length}
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
        <button type="button" onClick={onAddToMeld}>
          Добавить сюда
        </button>
      )}
    </div>
  )
}
