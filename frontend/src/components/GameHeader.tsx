interface GameHeaderProps {
  scores: Record<string, number>
  targetScore: number
}

export function GameHeader({ scores, targetScore }: GameHeaderProps) {
  return (
    <header>
      <ul aria-label="scores" className="game-header">
        {Object.entries(scores).map(([teamId, score]) => {
          const pct = Math.min(100, Math.round((Math.max(0, score) / targetScore) * 100))
          return (
            <li key={teamId} className="score-card">
              <span className="score-card-value">
                Команда {teamId}: {score} / {targetScore}
              </span>
              <span className="score-bar-track">
                <span className="score-bar-fill" style={{ width: `${pct}%` }} />
              </span>
            </li>
          )
        })}
      </ul>
    </header>
  )
}
