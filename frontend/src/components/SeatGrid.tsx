import type { LobbyPlayer } from '../lib/protocol'

const SEATS = [0, 1, 2, 3] as const

interface SeatGridProps {
  players: LobbyPlayer[]
  hostId: string | null
  isHost: boolean
  onAssignSeat: (playerId: string, seat: number) => void
}

function playerLabel(player: LobbyPlayer, hostId: string | null): string {
  const host = player.id === hostId ? ' (хост)' : ''
  const status = player.connected ? 'в сети' : 'офлайн'
  return `${player.name}${host} — ${status}`
}

export function SeatGrid({ players, hostId, isHost, onAssignSeat }: SeatGridProps) {
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
                <span>{playerLabel(player, hostId)}</span>
              ) : isHost ? (
                <label>
                  Место {seat + 1}:{' '}
                  <select
                    value=""
                    aria-label={`Посадить на место ${seat + 1}`}
                    onChange={(event) => {
                      if (event.target.value) {
                        onAssignSeat(event.target.value, seat)
                      }
                    }}
                  >
                    <option value="">свободно</option>
                    {players.map((candidate) => (
                      <option key={candidate.id} value={candidate.id}>
                        {candidate.name}
                      </option>
                    ))}
                  </select>
                </label>
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
              <li key={player.id}>{playerLabel(player, hostId)}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
