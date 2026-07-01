import { beforeEach, describe, expect, it } from 'vitest'
import { useChatStore } from './chatStore'

describe('useChatStore', () => {
  beforeEach(() => {
    useChatStore.getState().reset()
  })

  it('appends incoming messages and counts them as unread', () => {
    useChatStore.getState().addMessage({ from: 'p1', text: 'hi', ts: '2026-01-01T00:00:00Z' })
    useChatStore.getState().addMessage({ from: 'p2', text: 'hey', ts: '2026-01-01T00:00:01Z' })

    const state = useChatStore.getState()
    expect(state.messages).toHaveLength(2)
    expect(state.unread).toBe(2)
  })

  it('clears unread count on markRead without dropping messages', () => {
    useChatStore.getState().addMessage({ from: 'p1', text: 'hi', ts: '2026-01-01T00:00:00Z' })
    useChatStore.getState().markRead()

    const state = useChatStore.getState()
    expect(state.unread).toBe(0)
    expect(state.messages).toHaveLength(1)
  })
})
