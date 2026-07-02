import { beforeEach, describe, expect, it } from 'vitest'
import { useLobbyStore } from './lobbyStore'

describe('useLobbyStore', () => {
  beforeEach(() => {
    useLobbyStore.getState().reset()
  })

  it('applies a lobby_state payload verbatim', () => {
    useLobbyStore.getState().applyLobbyState({
      players: [
        {
          id: 'p1',
          name: 'Alice',
          seat: 0,
          team_id: 'A',
          connected: true,
          is_host: true,
          is_bot: false,
        },
      ],
      settings: { target_score: 3000, discard_visibility: 'FULL' },
      host_id: 'p1',
    })

    const state = useLobbyStore.getState()
    expect(state.hostId).toBe('p1')
    expect(state.players).toHaveLength(1)
    expect(state.players[0].name).toBe('Alice')
    expect(state.settings).toEqual({ targetScore: 3000, discardVisibility: 'FULL' })
  })

  it('reset clears back to the initial empty lobby', () => {
    useLobbyStore.getState().applyLobbyState({
      players: [
        { id: 'p1', name: 'Alice', seat: 0, team_id: 'A', connected: true, is_host: true, is_bot: false },
      ],
      settings: { target_score: 3000, discard_visibility: 'FULL' },
      host_id: 'p1',
    })

    useLobbyStore.getState().reset()

    const state = useLobbyStore.getState()
    expect(state.players).toEqual([])
    expect(state.hostId).toBeNull()
    expect(state.settings).toEqual({ targetScore: 5000, discardVisibility: 'TOP_ONLY' })
  })
})
