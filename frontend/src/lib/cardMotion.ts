// Shared framer-motion tuning for card "flight" (magic-move) animations: a
// card keeps its layoutId as it moves between hand / discard / melds, so
// framer-motion interpolates its position+size across component boundaries
// instead of it just popping into place.
export const CARD_FLIGHT_TRANSITION = {
  type: 'spring',
  stiffness: 380,
  damping: 32,
  mass: 0.7,
} as const

// Starting point for cards with no prior tracked position (drawn from the
// deck) -- dealt in from above rather than just appearing.
export const CARD_ENTER_FROM = { opacity: 0, y: -28, scale: 0.82 } as const
export const CARD_ENTER_TO = { opacity: 1, y: 0, scale: 1 } as const

export function cardLayoutId(cardId: string): string {
  return `card-${cardId}`
}
