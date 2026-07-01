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

// Client-side stand-in for a real action feed: the server only ever sends
// full snapshots (plan section 8), no discrete action events, so this logs
// the notable *messages* that arrive rather than diffed game state.
export const useEventLogStore = create<EventLogStore>((set) => ({
  entries: [],

  addEntry: (text) =>
    set((s) => ({
      entries: [...s.entries, { id: `e${nextId++}`, text }].slice(-MAX_ENTRIES),
    })),

  reset: () => set({ entries: [] }),
}))
