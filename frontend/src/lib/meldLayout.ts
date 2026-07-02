/** Tighter overlap for long melds so a 7-card canasta stays compact on the table. */
export function meldCardOverlapPx(cardCount: number, cardWidth = 78): number {
  if (cardCount <= 1) return 0
  const maxStripWidth = 260
  const minStep = 14
  const step = Math.max(minStep, (maxStripWidth - cardWidth) / (cardCount - 1))
  return Math.max(0, Math.round(cardWidth - step))
}
