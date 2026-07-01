interface GameHeaderProps {
  scores: Record<string, number>
  targetScore: number
  turnPlayerId: string
  turnPhase: string
  viewerId: string | null
  playerNames: Record<string, string>
}

const PHASE_LABELS: Record<string, string> = {
  DRAW: 'берёт карту',
  ACT: 'выкладывает/сбрасывает',
  DEAL_END: 'сдача завершена',
}

export function GameHeader({
  scores,
  targetScore,
  turnPlayerId,
  turnPhase,
  viewerId,
  playerNames,
}: GameHeaderProps) {
  const isMyTurn = viewerId !== null && viewerId === turnPlayerId
  const turnPlayerName = playerNames[turnPlayerId] ?? turnPlayerId
  const phaseLabel = PHASE_LABELS[turnPhase] ?? turnPhase

  return (
    <header>
      <ul aria-label="scores">
        {Object.entries(scores).map(([teamId, score]) => (
          <li key={teamId}>
            Команда {teamId}: {score} / {targetScore}
          </li>
        ))}
      </ul>
      <p>{isMyTurn ? 'Ваш ход' : `Ходит ${turnPlayerName}`} — {phaseLabel}</p>
    </header>
  )
}
