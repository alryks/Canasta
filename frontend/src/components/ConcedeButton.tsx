interface ConcedeButtonProps {
  visible: boolean
  onConcede: () => void
}

// FR-22.1/22.2 "не могу выложить" -- the one control that stays a button
// instead of a drag gesture even after phase 9, since it's a deliberate
// escape hatch (forces DISCARD, -1000 penalty), not a card move. Shown only
// while plausibly needed (own team not yet opened); the server doesn't
// expose must_meld_after_pickup/pending_penalty for a precise check, but
// concede_penalty itself is always safe to send on your own ACT turn.
export function ConcedeButton({ visible, onConcede }: ConcedeButtonProps) {
  if (!visible) return null

  return (
    <button type="button" onClick={onConcede}>
      Не могу выложить
    </button>
  )
}
