import { create } from 'zustand'
import type { DealResultMessage, DealScoreBreakdown, GameStateData } from '../lib/protocol'

interface DealResult {
  dealNumber: number
  scoresBreakdown: Record<string, DealScoreBreakdown>
  teamScoresAfter: Record<string, number>
  nextDeal: boolean
}

interface GameStore {
  state: GameStateData | null
  lastDealResult: DealResult | null
  winnerTeamId: string | null
  lastActionError: string | null
  applyGameState: (data: GameStateData) => void
  applyDealResult: (data: DealResultMessage['data']) => void
  applyGameOver: (winnerTeamId: string) => void
  applyActionError: (reason: string) => void
  dismissActionError: () => void
  dismissDealResult: () => void
  reset: () => void
}

// Mirrors the server's game_state verbatim (plan section 14, useGameStore):
// mutated only by the WS message handler, never directly by components.
export const useGameStore = create<GameStore>((set) => ({
  state: null,
  lastDealResult: null,
  winnerTeamId: null,
  lastActionError: null,

  applyGameState: (data) => set({ state: data, lastActionError: null }),

  applyDealResult: (data) =>
    set({
      lastDealResult: {
        dealNumber: data.deal_number,
        scoresBreakdown: data.scores_breakdown,
        teamScoresAfter: data.team_scores_after,
        nextDeal: data.next_deal,
      },
    }),

  applyGameOver: (winnerTeamId) => set({ winnerTeamId }),

  applyActionError: (reason) => set({ lastActionError: reason }),
  dismissActionError: () => set({ lastActionError: null }),
  dismissDealResult: () => set({ lastDealResult: null }),

  reset: () =>
    set({
      state: null,
      lastDealResult: null,
      winnerTeamId: null,
      lastActionError: null,
    }),
}))
