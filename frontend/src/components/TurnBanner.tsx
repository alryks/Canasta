import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'

interface TurnBannerProps {
  turnPlayerId: string
  viewerId: string | null
  turnPhase: string
  playerNames: Record<string, string>
}

const PHASE_LABELS: Record<string, string> = {
  DRAW: 'берёт карту',
  ACT: 'выкладывает/сбрасывает',
  DEAL_END: 'сдача завершена',
}

export function TurnBanner({
  turnPlayerId,
  viewerId,
  turnPhase,
  playerNames,
}: TurnBannerProps) {
  const isMyTurn = viewerId !== null && viewerId === turnPlayerId
  const turnPlayerName = playerNames[turnPlayerId] ?? turnPlayerId
  const phaseLabel = PHASE_LABELS[turnPhase] ?? turnPhase

  // A flash on the whole banner, but only for an actual turn handoff -- not
  // for a phase change (DRAW -> ACT) within the same player's turn, which
  // shouldn't compete for attention the same way "it's someone else's turn
  // now" should.
  const [prevTurnPlayerId, setPrevTurnPlayerId] = useState(turnPlayerId)
  const [justHandedOff, setJustHandedOff] = useState(false)
  if (turnPlayerId !== prevTurnPlayerId) {
    setPrevTurnPlayerId(turnPlayerId)
    setJustHandedOff(true)
  }
  useEffect(() => {
    if (!justHandedOff) return
    const id = window.setTimeout(() => setJustHandedOff(false), 900)
    return () => window.clearTimeout(id)
  }, [justHandedOff])

  return (
    <p
      className={`turn-banner${isMyTurn ? ' is-my-turn' : ''}${
        justHandedOff ? ' is-turn-handoff' : ''
      }`}
      role="status"
    >
      <motion.span
        key={turnPlayerId}
        className="turn-banner-name"
        initial={{ opacity: 0, y: -14, scale: 0.85 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: 'spring', stiffness: 360, damping: 22 }}
      >
        {isMyTurn ? 'Ваш ход' : `Ходит ${turnPlayerName}`}
      </motion.span>
      {' — '}
      {phaseLabel}
    </p>
  )
}
