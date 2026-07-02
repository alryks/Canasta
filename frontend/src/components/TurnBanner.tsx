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
    <p className={`turn-banner${isMyTurn ? ' is-my-turn' : ''}`} role="status">
      {isMyTurn ? 'Ваш ход' : `Ходит ${turnPlayerName}`} — {phaseLabel}
    </p>
  )
}
