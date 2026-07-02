interface GameOverModalProps {
  winnerTeamId: string
  finalScores: Record<string, number>
}

export function GameOverModal({ winnerTeamId, finalScores }: GameOverModalProps) {
  return (
    <div className="modal-overlay">
      <div role="dialog" aria-label="game-over" className="panel modal-panel">
        <h1>🏆 Игра окончена</h1>
        <p>Победила команда {winnerTeamId}</p>
        <ul aria-label="final-scores" className="final-score-list">
          {Object.entries(finalScores).map(([teamId, score]) => (
            <li key={teamId} className="score-card">
              <span className="score-card-value">
                Команда {teamId}: {score}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
