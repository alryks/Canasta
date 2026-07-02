import { useEffect, useState } from 'react'

const DISARM_MS = 4000

interface ConcedeButtonProps {
  visible: boolean
  onConcede: () => void
}

// FR-22.1/22.2 "не могу выложить": shown only when the player is actually
// stuck (took the discard pile and can't lay the required meld / can't cover
// the opening threshold -- GamePage computes that from the turn flags).
// Costs -1000, so it takes a second confirming click; arming times out.
export function ConcedeButton({ visible, onConcede }: ConcedeButtonProps) {
  const [armed, setArmed] = useState(false)

  useEffect(() => {
    if (!armed) return
    const id = setTimeout(() => setArmed(false), DISARM_MS)
    return () => clearTimeout(id)
  }, [armed])

  useEffect(() => {
    if (!visible) setArmed(false)
  }, [visible])

  if (!visible) return null

  if (!armed) {
    return (
      <button type="button" className="btn btn-danger" onClick={() => setArmed(true)}>
        Штраф −1000
      </button>
    )
  }

  return (
    <button
      type="button"
      className="btn btn-danger is-armed"
      onClick={() => {
        setArmed(false)
        onConcede()
      }}
    >
      Подтвердить
    </button>
  )
}
