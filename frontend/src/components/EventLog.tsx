import { useState } from 'react'
import type { EventLogEntry } from '../stores/eventLogStore'

interface EventLogProps {
  entries: EventLogEntry[]
}

export function EventLog({ entries }: EventLogProps) {
  const [open, setOpen] = useState(false)

  return (
    <div className="table-tool">
      {open && (
        <div className="modal-overlay" role="dialog" aria-label="event-log-modal">
          <div className="panel modal-panel log-modal">
            <div className="modal-header">
              <h3>События</h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setOpen(false)}
                aria-label="Закрыть"
              >
                ×
              </button>
            </div>
            <ul aria-label="event-log" className="modal-messages">
              {entries.map((entry) => (
                <li key={entry.id}>{entry.text}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      <button
        type="button"
        className="btn btn-ghost table-tool-btn"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        События {entries.length}
      </button>
    </div>
  )
}
