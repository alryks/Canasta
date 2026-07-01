import { create } from 'zustand'
import type { LobbyPlayer, LobbyStateMessage } from '../lib/protocol'

interface LobbySettings {
  targetScore: number
  discardVisibility: string
}

interface LobbyStore {
  players: LobbyPlayer[]
  hostId: string | null
  settings: LobbySettings
  applyLobbyState: (data: LobbyStateMessage['data']) => void
  reset: () => void
}

const initialSettings: LobbySettings = {
  targetScore: 5000,
  discardVisibility: 'TOP_ONLY',
}

export const useLobbyStore = create<LobbyStore>((set) => ({
  players: [],
  hostId: null,
  settings: initialSettings,

  applyLobbyState: (data) =>
    set({
      players: data.players,
      hostId: data.host_id,
      settings: {
        targetScore: data.settings.target_score,
        discardVisibility: data.settings.discard_visibility,
      },
    }),

  reset: () => set({ players: [], hostId: null, settings: initialSettings }),
}))
