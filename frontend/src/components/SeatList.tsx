import type { LobbyPlayer } from '../lib/protocol'

const SEATS = [0, 1, 2, 3] as const

interface SeatListProps {
  players: LobbyPlayer[]
  hostId: string | null
}

export function SeatList({ players, hostId }: SeatListProps) {
  const bySeat = new Map(players.filter((p) => p.seat !== null).map((p) => [p.seat, p]))
  const unseated = players.filter((p) => p.seat === null)

  return (
    <div>
      <ul aria-label="seats">
        {SEATS.map((seat) => {
          const player = bySeat.get(seat)
          return (
            <li key={seat} data-seat={seat}>
              {player ? (
                <span>
                  {player.name}
                  {player.id === hostId ? ' (хост)' : ''}
                  {' — '}
                  {player.connected ? 'в сети' : 'офлайн'}
                </span>
              ) : (
                <span>Место {seat + 1}: свободно</span>
              )}
            </li>
          )
        })}
      </ul>

      {unseated.length > 0 && (
        <div>
          <p>Ожидают места:</p>
          <ul aria-label="unseated">
            {unseated.map((player) => (
              <li key={player.id}>
                {player.name}
                {player.id === hostId ? ' (хост)' : ''}
                {' — '}
                {player.connected ? 'в сети' : 'офлайн'}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
