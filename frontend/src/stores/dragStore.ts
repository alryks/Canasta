import { create } from 'zustand'

export type DragOrigin = 'hand' | 'discard'

interface DragStore {
  cardId: string | null
  origin: DragOrigin | null
  pointer: { x: number; y: number }
  hoveredZone: string | null
  startDrag: (cardId: string, origin: DragOrigin, x: number, y: number) => void
  moveDrag: (x: number, y: number, hoveredZone: string | null) => void
  endDrag: () => void
}

// Ephemeral, never synced with the server (plan section 14) -- reset on
// every pointerup/cancel so a rejected drop just snaps the card back with
// no risk of desyncing useGameStore.
export const useDragStore = create<DragStore>((set) => ({
  cardId: null,
  origin: null,
  pointer: { x: 0, y: 0 },
  hoveredZone: null,

  startDrag: (cardId, origin, x, y) =>
    set({ cardId, origin, pointer: { x, y }, hoveredZone: null }),

  moveDrag: (x, y, hoveredZone) => set({ pointer: { x, y }, hoveredZone }),

  endDrag: () => set({ cardId: null, origin: null, hoveredZone: null }),
}))
