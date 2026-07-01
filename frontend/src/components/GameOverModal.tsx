interface GameOverModalProps {
  winnerTeamId: string
  finalScores: Record<string, number>
}

export function GameOverModal({ winnerTeamId, finalScores }: GameOverModalProps) {
  return (
    <div role="dialog" aria-label="game-over">
      <h1>Игра окончена</h1>
      <p>Победила команда {winnerTeamId}</p>
      <ul aria-label="final-scores">
        {Object.entries(finalScores).map(([teamId, score]) => (
          <li key={teamId}>
            Команда {teamId}: {score}
          </li>
        ))}
      </ul>
    </div>
  )
}
