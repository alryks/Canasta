import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { GameStateData } from '../lib/protocol'
import { useChatStore } from '../stores/chatStore'
import { useConnectionStore } from '../stores/connectionStore'
import { useEventLogStore } from '../stores/eventLogStore'
import { useGameStore } from '../stores/gameStore'
import { useLobbyStore } from '../stores/lobbyStore'
import { GamePage } from './GamePage'

function baseGameState(overrides: Partial<GameStateData> = {}): GameStateData {
  return {
    hands: {
      p1: [
        { id: 'c1', rank: '7', suit: 'HEARTS' },
        { id: 'c2', rank: '7', suit: 'CLUBS' },
      ],
      p2: 10,
      p3: 11,
      p4: 11,
    },
    melds: {
      A: [],
      B: [
        {
          id: 'm1',
          team_id: 'B',
          kind: 'SET',
          rank_or_suit_anchor: '8',
          slots: [
            { id: 'w1', rank: 'JOKER', suit: null },
            { id: 'w2', rank: '8', suit: 'SPADES' },
            { id: 'w3', rank: '8', suit: 'HEARTS' },
          ],
        },
      ],
    },
    deck_count: 40,
    discard_pile: [],
    scores: { A: 0, B: 0 },
    thresholds: { A: 50, B: 50 },
    turn_player_id: 'p1',
    turn_phase: 'ACT',
    turn_accumulator: { A: 0, B: 0 },
    ...overrides,
  }
}

function setupPlayers() {
  useLobbyStore.setState({
    players: [
      { id: 'p1', name: 'Alice', seat: 0, team_id: 'A', connected: true, is_host: true },
      { id: 'p2', name: 'Bob', seat: 1, team_id: 'B', connected: true, is_host: false },
      { id: 'p3', name: 'Carol', seat: 2, team_id: 'A', connected: true, is_host: false },
      { id: 'p4', name: 'Dave', seat: 3, team_id: 'B', connected: true, is_host: false },
    ],
    hostId: 'p1',
    settings: { targetScore: 5000, discardVisibility: 'TOP_ONLY' },
  })
}

describe('GamePage', () => {
  let send: ReturnType<
    typeof vi.fn<(type: string, data?: Record<string, unknown>) => void>
  >

  beforeEach(() => {
    useGameStore.getState().reset()
    useChatStore.getState().reset()
    useEventLogStore.getState().reset()
    setupPlayers()
    send = vi.fn()
    useConnectionStore.setState({
      status: 'open',
      gameId: 'g1',
      playerId: 'p1',
      send,
    })
  })

  it('shows a loading placeholder before the first game_state arrives', () => {
    render(<GamePage />)
    expect(screen.getByText(/Загрузка/)).toBeInTheDocument()
  })

  it("renders own hand, opponent counts, and the deck/discard summary", () => {
    useGameStore.getState().applyGameState(baseGameState())
    render(<GamePage />)

    expect(screen.getByText('7♥')).toBeInTheDocument()
    expect(screen.getByText('7♣')).toBeInTheDocument()
    expect(screen.getByText(/Bob: 10 карт/)).toBeInTheDocument()
    expect(screen.getByText(/Колода: 40 карт/)).toBeInTheDocument()
  })

  it('sends draw_deck when drawing during the DRAW phase on my turn', async () => {
    useGameStore.getState().applyGameState(baseGameState({ turn_phase: 'DRAW' }))
    render(<GamePage />)

    await userEvent.click(screen.getByText('Взять из колоды'))
    expect(send).toHaveBeenCalledWith('draw_deck', {})
  })

  it('creates a meld from selected hand cards and clears the selection', async () => {
    useGameStore.getState().applyGameState(baseGameState())
    render(<GamePage />)

    await userEvent.click(screen.getByText('7♥'))
    await userEvent.click(screen.getByText('7♣'))
    await userEvent.click(screen.getByText('Выложить новый мелд'))

    expect(send).toHaveBeenCalledWith('create_meld', { card_ids: ['c1', 'c2'] })
    expect(screen.getByText('7♥')).toHaveAttribute('aria-pressed', 'false')
  })

  it('only enables discard once exactly one card is selected', async () => {
    useGameStore.getState().applyGameState(baseGameState())
    render(<GamePage />)

    const discardButton = screen.getByText('Сбросить')
    expect(discardButton).toBeDisabled()

    await userEvent.click(screen.getByText('7♥'))
    expect(discardButton).toBeEnabled()

    await userEvent.click(discardButton)
    expect(send).toHaveBeenCalledWith('discard', { card_id: 'c1' })
  })

  it('steals a wild card from an opponent meld using a selected hand card', async () => {
    useGameStore.getState().applyGameState(baseGameState())
    render(<GamePage />)

    await userEvent.click(screen.getByText(/SET 8/))
    await userEvent.click(screen.getByText('JOKER'))
    await userEvent.click(screen.getByText('7♥'))
    await userEvent.click(screen.getByText('Украсть козырь'))

    expect(send).toHaveBeenCalledWith('steal_wild', {
      meld_id: 'm1',
      wild_card_id: 'w1',
      replacement_card_id: 'c1',
    })
  })

  it("shows the threshold indicator and concede button while the viewer's team is not opened", () => {
    useGameStore
      .getState()
      .applyGameState(baseGameState({ turn_accumulator: { A: 15, B: 0 } }))
    render(<GamePage />)

    expect(screen.getByLabelText('threshold-A')).toHaveTextContent('15/50')
    expect(screen.getByText('Не могу выложить')).toBeInTheDocument()
  })

  it("hides the threshold indicator and concede button once the viewer's team is opened", () => {
    useGameStore
      .getState()
      .applyGameState(baseGameState({ turn_accumulator: { A: 50, B: 0 } }))
    render(<GamePage />)

    expect(screen.queryByLabelText('threshold-A')).not.toBeInTheDocument()
    expect(screen.queryByText('Не могу выложить')).not.toBeInTheDocument()
  })

  it('shows the winner once the game is over and hides interactive controls', () => {
    useGameStore.getState().applyGameState(baseGameState({ scores: { A: 5200, B: 1100 } }))
    useGameStore.getState().applyGameOver('A')
    render(<GamePage />)

    expect(screen.getByText(/Игра окончена/)).toBeInTheDocument()
    expect(screen.getByText(/Победила команда A/)).toBeInTheDocument()
    expect(screen.queryByLabelText('actions')).not.toBeInTheDocument()
  })

  it('prefers the final deal result scores over the possibly stale game_state scores', () => {
    useGameStore.getState().applyGameState(baseGameState({ scores: { A: 4200, B: 1100 } }))
    useGameStore.getState().applyDealResult({
      deal_number: 5,
      scores_breakdown: {
        A: {
          table_points: 200,
          canasta_bonus: 500,
          hand_penalty: 0,
          three_bonus: 100,
          exit_bonus: 200,
          total: 1000,
        },
      },
      team_scores_after: { A: 5200, B: 1100 },
      next_deal: false,
    })
    useGameStore.getState().applyGameOver('A')
    render(<GamePage />)

    const finalScores = screen.getByLabelText('final-scores')
    expect(finalScores).toHaveTextContent('Команда A: 5200')
  })

  it('shows the deal result modal and dismisses it on click', async () => {
    useGameStore.getState().applyGameState(baseGameState())
    useGameStore.getState().applyDealResult({
      deal_number: 1,
      scores_breakdown: {
        A: {
          table_points: 200,
          canasta_bonus: 500,
          hand_penalty: 0,
          three_bonus: 100,
          exit_bonus: 200,
          total: 1000,
        },
      },
      team_scores_after: { A: 1000, B: 0 },
      next_deal: true,
    })
    render(<GamePage />)

    expect(screen.getByText('Сдача №1 завершена')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Продолжить'))
    expect(screen.queryByText('Сдача №1 завершена')).not.toBeInTheDocument()
  })

  it('logs notable events and sends chat messages', async () => {
    useGameStore.getState().applyGameState(baseGameState())
    useEventLogStore.getState().addEntry('Bob подключился')
    render(<GamePage />)

    await userEvent.click(screen.getByText('Лента событий (1)'))
    expect(screen.getByText('Bob подключился')).toBeInTheDocument()

    await userEvent.click(screen.getByText('Чат'))
    await userEvent.type(screen.getByLabelText('Сообщение'), 'привет')
    await userEvent.click(screen.getByText('Отправить'))

    expect(send).toHaveBeenCalledWith('send_chat', { text: 'привет' })
  })
})
