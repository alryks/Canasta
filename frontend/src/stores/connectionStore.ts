import { create } from 'zustand'
import { wsUrl } from '../lib/api'
import type { ServerMessage } from '../lib/protocol'

export type ConnectionStatus = 'idle' | 'connecting' | 'open' | 'closed' | 'error'

interface ConnectionStore {
  status: ConnectionStatus
  gameId: string | null
  playerId: string | null
  connect: (
    gameId: string,
    playerId: string,
    sessionToken: string,
    onMessage: (message: ServerMessage) => void,
  ) => void
  send: (type: string, data?: Record<string, unknown>) => void
  disconnect: () => void
}

// The live socket is intentionally kept outside the store's state: it's not
// serializable and components never need to read it directly, only send
// through it -- keeping it out avoids re-renders on every socket event.
let socket: WebSocket | null = null

export const useConnectionStore = create<ConnectionStore>((set, get) => ({
  status: 'idle',
  gameId: null,
  playerId: null,

  connect: (gameId, playerId, sessionToken, onMessage) => {
    if (socket && get().gameId === gameId && get().status !== 'closed') {
      return
    }
    socket?.close()

    set({ status: 'connecting', gameId, playerId })
    const ws = new WebSocket(wsUrl(gameId, sessionToken))
    socket = ws

    ws.onopen = () => set({ status: 'open' })
    ws.onclose = () => set({ status: 'closed' })
    ws.onerror = () => set({ status: 'error' })
    ws.onmessage = (event) => {
      onMessage(JSON.parse(event.data) as ServerMessage)
    }
  },

  send: (type, data = {}) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type, data }))
    }
  },

  disconnect: () => {
    socket?.close()
    socket = null
    set({ status: 'idle', gameId: null, playerId: null })
  },
}))
