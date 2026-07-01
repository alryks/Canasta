import { useState } from 'react'
import type { EventLogEntry } from '../stores/eventLogStore'

interface EventLogProps {
  entries: EventLogEntry[]
}

export function EventLog({ entries }: EventLogProps) {
  const [open, setOpen] = useState(false)

  return (
    <div>
      <button type="button" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        Лента событий ({entries.length})
      </button>
      {open && (
        <ul aria-label="event-log">
          {entries.map((entry) => (
            <li key={entry.id}>{entry.text}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
