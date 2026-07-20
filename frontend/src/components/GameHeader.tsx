interface GameHeaderProps {
  scores: Record<string, number>
  targetScore: number
  viewerTeamId: string | null
}

export function GameHeader({ scores, targetScore, viewerTeamId }: GameHeaderProps) {
  const teamScores = Object.entries(scores).sort(
    ([leftTeamId], [rightTeamId]) =>
      Number(rightTeamId === viewerTeamId) - Number(leftTeamId === viewerTeamId),
  )

  return (
    <header>
      <ul aria-label="scores" className="game-header">
        {teamScores.map(([teamId, score]) => {
          const pct = Math.min(100, Math.round((Math.max(0, score) / targetScore) * 100))
          const isViewerTeam = teamId === viewerTeamId
          const label = isViewerTeam ? 'Ваша команда' : 'Команда соперников'
          const tooltipId = `score-tooltip-${teamId}`
          return (
            <li
              key={teamId}
              className="score-card"
              tabIndex={0}
              aria-label={`${label}: ${score} из ${targetScore} очков`}
              aria-describedby={tooltipId}
            >
              <span className="score-card-value">{label}</span>
              <span
                className="score-bar-track"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={targetScore}
                aria-valuenow={score}
              >
                <span className="score-bar-fill" style={{ width: `${pct}%` }} />
              </span>
              <span id={tooltipId} role="tooltip" className="score-card-tooltip">
                {score} из {targetScore} очков
              </span>
            </li>
          )
        })}
      </ul>
    </header>
  )
}
