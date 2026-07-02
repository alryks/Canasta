import { create } from 'zustand'

export interface EventLogEntry {
  id: string
  text: string
}

interface EventLogStore {
  entries: EventLogEntry[]
  addEntry: (text: string) => void
  reset: () => void
}

const MAX_ENTRIES = 50
let nextId = 0

// Client-side action feed: the server sends full snapshots, so GameRoute logs
// both notable messages and gameplay events inferred from adjacent snapshots.
export const useEventLogStore = create<EventLogStore>((set) => ({
  entries: [],

  addEntry: (text) =>
    set((s) => ({
      entries: [...s.entries, { id: `e${nextId++}`, text }].slice(-MAX_ENTRIES),
    })),

  reset: () => set({ entries: [] }),
}))
