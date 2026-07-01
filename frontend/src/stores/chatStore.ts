import { create } from 'zustand'
import type { ChatMessageMessage } from '../lib/protocol'

type ChatMessageEntry = ChatMessageMessage['data']

interface ChatStore {
  messages: ChatMessageEntry[]
  unread: number
  addMessage: (message: ChatMessageEntry) => void
  markRead: () => void
  reset: () => void
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  unread: 0,

  addMessage: (message) =>
    set((s) => ({ messages: [...s.messages, message], unread: s.unread + 1 })),

  markRead: () => set({ unread: 0 }),

  reset: () => set({ messages: [], unread: 0 }),
}))
