interface GameHeaderProps {
  scores: Record<string, number>
  targetScore: number
}

export function GameHeader({ scores, targetScore }: GameHeaderProps) {
  return (
    <header>
      <ul aria-label="scores">
        {Object.entries(scores).map(([teamId, score]) => (
          <li key={teamId}>
            Команда {teamId}: {score} / {targetScore}
          </li>
        ))}
      </ul>
    </header>
  )
}
