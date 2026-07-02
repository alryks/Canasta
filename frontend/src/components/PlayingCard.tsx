import type { PointerEventHandler } from 'react'
import { isRedSuit, suitSymbol } from '../lib/cards'
import type { Card } from '../lib/protocol'

interface PlayingCardProps {
  card?: Card
  faceDown?: boolean
  empty?: boolean
  size?: 'normal' | 'small'
  selected?: boolean
  wild?: boolean
  className?: string
  onClick?: () => void
  pressed?: boolean
  disabled?: boolean
  ariaLabel?: string
  onPointerDown?: PointerEventHandler
  dropZone?: string
  dragging?: boolean
}

// Casino-style card face: rank+suit corner indices (mirrored bottom-right),
// large center suit glyph. Rendered purely with CSS/text -- no image assets
// (plan section 8/17 only fixes the palette, not a specific art asset).
export function PlayingCard({
  card,
  faceDown = false,
  empty = false,
  size = 'normal',
  selected = false,
  wild = false,
  className = '',
  onClick,
  pressed,
  disabled = false,
  ariaLabel,
  onPointerDown,
  dropZone,
  dragging = false,
}: PlayingCardProps) {
  const classes = [
    'playing-card',
    empty ? 'is-empty-slot' : faceDown || !card ? 'is-back' : 'is-face',
    !faceDown && card && isRedSuit(card.suit) ? 'is-red' : '',
    size === 'small' ? 'is-small' : '',
    selected ? 'is-selected' : '',
    wild ? 'is-wild' : '',
    onClick ? 'is-selectable' : '',
    dragging ? 'is-dragging-source' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  const isJoker = card?.rank === 'JOKER'
  const content = empty ? (
    <span className="card-center">—</span>
  ) : !faceDown && card ? (
    <>
      <span className="card-index">{isJoker ? '★' : `${card.rank}${suitSymbol(card.suit)}`}</span>
      <span className={`card-center${isJoker ? ' is-joker' : ''}`}>
        {isJoker ? 'JOKER' : suitSymbol(card.suit)}
      </span>
    </>
  ) : null

  if (onClick) {
    return (
      <button
        type="button"
        className="card-slot-btn"
        onClick={onClick}
        onPointerDown={onPointerDown}
        aria-pressed={pressed}
        disabled={disabled}
        aria-label={ariaLabel}
        data-drop-zone={dropZone}
      >
        <span className={classes}>{content}</span>
      </button>
    )
  }

  return (
    <span
      className={classes}
      aria-label={ariaLabel}
      onPointerDown={onPointerDown}
      data-drop-zone={dropZone}
    >
      {content}
    </span>
  )
}
