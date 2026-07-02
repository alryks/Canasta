import { useState } from 'react'
import type { LobbyPlayer } from '../lib/protocol'
import { SeatAssignModal } from './SeatAssignModal'

const SEATS = [0, 1, 2, 3] as const

interface SeatGridProps {
  players: LobbyPlayer[]
  hostId: string | null
  isHost: boolean
  onAssignSeat: (playerId: string, seat: number) => void
  onAddBot: (seat: number) => void
}

function statusLabel(player: LobbyPlayer): string {
  if (player.is_bot) return 'бот'
  return player.connected ? 'в сети' : 'офлайн'
}

export function SeatGrid({ players, hostId, isHost, onAssignSeat, onAddBot }: SeatGridProps) {
  const [assignSeat, setAssignSeat] = useState<number | null>(null)
  const bySeat = new Map(players.filter((p) => p.seat !== null).map((p) => [p.seat, p]))
  const unseated = players.filter((p) => p.seat === null)

  return (
    <div>
      <ul aria-label="seats" className="seat-grid">
        {SEATS.map((seat) => {
          const player = bySeat.get(seat)
          return (
            <li key={seat} data-seat={seat} className={`seat-card${player ? ' is-filled' : ''}`}>
              <span className="seat-label">Место {seat + 1}</span>
              {player ? (
                <>
                  <span className="seat-player-name">{player.name}</span>
                  <span className="seat-player-meta">
                    {player.id === hostId && <span className="host-tag">хост</span>}
                    <span
                      className={`online-tag ${
                        player.is_bot ? 'is-bot' : player.connected ? 'is-online' : 'is-offline'
                      }`}
                    >
                      {statusLabel(player)}
                    </span>
                  </span>
                  {isHost && (
                    <button
                      type="button"
                      className="btn btn-ghost seat-change-btn"
                      onClick={() => setAssignSeat(seat)}
                    >
                      Сменить
                    </button>
                  )}
                </>
              ) : isHost ? (
                <button
                  type="button"
                  className="btn seat-open-btn"
                  onClick={() => setAssignSeat(seat)}
                >
                  Назначить
                </button>
              ) : (
                <span className="seat-free-label">свободно</span>
              )}
            </li>
          )
        })}
      </ul>

      {unseated.length > 0 && (
        <ul aria-label="unseated" className="unseated-list">
          {unseated.map((player) => (
            <li key={player.id} className="unseated-chip">
              {player.name}
              {player.id === hostId ? ' · хост' : ''}
              {' · '}
              {statusLabel(player)}
            </li>
          ))}
        </ul>
      )}

      {assignSeat !== null && (
        <SeatAssignModal
          seat={assignSeat}
          players={players}
          onAssign={(playerId) => onAssignSeat(playerId, assignSeat)}
          onAddBot={() => {
            onAddBot(assignSeat)
            setAssignSeat(null)
          }}
          onClose={() => setAssignSeat(null)}
        />
      )}
    </div>
  )
}
