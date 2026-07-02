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
  setPlayerConnected: (playerId: string, connected: boolean) => void
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

  // player_connection (FR-33/34) is the only signal for connect/disconnect
  // once the game has started -- lobby_state never arrives again after
  // LOBBY status, so this is the sole way the seat badges (is-offline) stay
  // accurate mid-game.
  setPlayerConnected: (playerId, connected) =>
    set((s) => ({
      players: s.players.map((p) => (p.id === playerId ? { ...p, connected } : p)),
    })),

  reset: () => set({ players: [], hostId: null, settings: initialSettings }),
}))
