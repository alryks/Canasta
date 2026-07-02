import type { LobbyPlayer } from '../lib/protocol'

const SEATS = [0, 1, 2, 3] as const

interface SeatGridProps {
  players: LobbyPlayer[]
  hostId: string | null
  isHost: boolean
  onAssignSeat: (playerId: string, seat: number) => void
  onAddBot: (seat: number) => void
}

function playerLabel(player: LobbyPlayer, hostId: string | null): string {
  const host = player.id === hostId ? ' (хост)' : ''
  const status = player.is_bot ? 'бот' : player.connected ? 'в сети' : 'офлайн'
  return `${player.name}${host} — ${status}`
}

export function SeatGrid({ players, hostId, isHost, onAssignSeat, onAddBot }: SeatGridProps) {
  const bySeat = new Map(players.filter((p) => p.seat !== null).map((p) => [p.seat, p]))
  const unseated = players.filter((p) => p.seat === null)

  return (
    <div>
      <ul aria-label="seats" className="seat-grid">
        {SEATS.map((seat) => {
          const player = bySeat.get(seat)
          return (
            <li key={seat} data-seat={seat} className={`seat-card${player ? ' is-filled' : ''}`}>
              {player ? (
                <>
                  <span className="seat-player-name">{player.name}</span>
                  <span>
                    {player.id === hostId && <span className="host-tag">хост</span>}{' '}
                    {player.is_bot ? (
                      <span className="online-tag is-bot">🤖 бот</span>
                    ) : (
                      <span
                        className={`online-tag ${player.connected ? 'is-online' : 'is-offline'}`}
                      >
                        {player.connected ? 'в сети' : 'офлайн'}
                      </span>
                    )}
                  </span>
                  <span className="visually-hidden">{playerLabel(player, hostId)}</span>
                </>
              ) : isHost ? (
                <>
                  <label>
                    <span className="seat-label">Место {seat + 1}</span>
                    <select
                      className="input"
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
                  <button
                    type="button"
                    className="btn btn-ghost btn-add-bot"
                    onClick={() => onAddBot(seat)}
                  >
                    🤖 Добавить бота
                  </button>
                </>
              ) : (
                <>
                  <span className="seat-label">Место {seat + 1}</span>
                  <span>свободно</span>
                </>
              )}
            </li>
          )
        })}
      </ul>

      {unseated.length > 0 && (
        <div>
          <p>Ожидают места:</p>
          <ul aria-label="unseated" className="unseated-list">
            {unseated.map((player) => (
              <li key={player.id} className="unseated-chip">
                {playerLabel(player, hostId)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
