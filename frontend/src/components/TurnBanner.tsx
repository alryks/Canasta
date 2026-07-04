import { AnimatePresence, motion } from 'framer-motion'

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

  return (
    <AnimatePresence mode="wait">
      <motion.p
        key={`${turnPlayerId}:${turnPhase}`}
        className={`turn-banner${isMyTurn ? ' is-my-turn' : ''}`}
        role="status"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 10 }}
        transition={{ duration: 0.22, ease: 'easeOut' }}
      >
        {isMyTurn ? 'Ваш ход' : `Ходит ${turnPlayerName}`} — {phaseLabel}
      </motion.p>
    </AnimatePresence>
  )
}
