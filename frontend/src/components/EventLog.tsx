import { useState } from 'react'
import type { EventLogEntry } from '../stores/eventLogStore'

interface EventLogProps {
  entries: EventLogEntry[]
}

export function EventLog({ entries }: EventLogProps) {
  const [open, setOpen] = useState(false)

  return (
    <div className="side-panel side-panel-log">
      {open && (
        <div className="side-panel-body">
          <ul aria-label="event-log" className="side-panel-messages">
            {entries.map((entry) => (
              <li key={entry.id}>{entry.text}</li>
            ))}
          </ul>
        </div>
      )}
      <button
        type="button"
        className="btn btn-ghost"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        Лента событий ({entries.length})
      </button>
    </div>
  )
}
