import type { LobbyPlayer } from '../lib/protocol'

interface SeatAssignModalProps {
  seat: number
  players: LobbyPlayer[]
  onAssign: (playerId: string) => void
  onAddBot: () => void
  onClose: () => void
}

export function SeatAssignModal({
  seat,
  players,
  onAssign,
  onAddBot,
  onClose,
}: SeatAssignModalProps) {
  const occupant = players.find((p) => p.seat === seat)
  const candidates = players.filter((p) => p.seat !== seat)

  return (
    <div className="modal-overlay" role="dialog" aria-label={`seat-assign-${seat}`}>
      <div className="panel seat-assign-panel">
        <h3>Место {seat + 1}</h3>
        <ul className="seat-assign-list">
          {candidates.map((player) => (
            <li key={player.id}>
              <button
                type="button"
                className="btn seat-assign-player"
                onClick={() => {
                  onAssign(player.id)
                  onClose()
                }}
              >
                <span className="seat-assign-name">{player.name}</span>
                {player.seat !== null && (
                  <span className="seat-assign-meta">место {player.seat + 1}</span>
                )}
                {player.is_host && <span className="host-tag">хост</span>}
              </button>
            </li>
          ))}
        </ul>
        {candidates.length === 0 && <p className="seat-assign-empty">Нет других игроков</p>}
        <div className="seat-assign-actions">
          {occupant === undefined && (
            <button type="button" className="btn" onClick={onAddBot}>
              Добавить бота
            </button>
          )}
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Отмена
          </button>
        </div>
      </div>
    </div>
  )
}
