// Server -> client WS messages (plan section 8). The server is the single
// source of truth and always sends full snapshots, never deltas.

export interface LobbyPlayer {
  id: string
  name: string
  seat: number | null
  team_id: string | null
  connected: boolean
  is_host: boolean
}

export interface LobbyStateMessage {
  type: 'lobby_state'
  data: {
    players: LobbyPlayer[]
    settings: { target_score: number; discard_visibility: string }
    host_id: string
  }
}

export interface PlayerConnectionMessage {
  type: 'player_connection'
  data: { player_id: string; connected: boolean }
}

export interface ActionErrorMessage {
  type: 'action_error'
  data: { reason: string }
}

export interface Card {
  id: string
  rank: string
  suit: string | null
}

export interface Meld {
  id: string
  team_id: string
  kind: string
  rank_or_suit_anchor: string
  slots: (Card | null)[]
}

// hands[playerId] is the viewer's own full hand, or another player's card
// count -- the server never sends other players' actual cards (NFR-3).
export interface GameStateData {
  hands: Record<string, Card[] | number>
  melds: Record<string, Meld[]>
  deck_count: number
  discard_pile: Card[]
  scores: Record<string, number>
  thresholds: Record<string, number>
  turn_player_id: string
  turn_phase: string
  turn_accumulator: Record<string, number>
}

export interface GameStateMessage {
  type: 'game_state'
  data: GameStateData
}

export interface DealResultMessage {
  type: 'deal_result'
  data: {
    deal_number: number
    scores_breakdown: Record<string, unknown>
    team_scores_after: Record<string, number>
    next_deal: boolean
  }
}

export interface GameOverMessage {
  type: 'game_over'
  data: { winner_team: string }
}

export interface TurnTimerExpiredMessage {
  type: 'turn_timer_expired'
  data: { player_id: string }
}

// player_connection and turn_timer_expired stay covered by OtherMessage for
// now -- nothing in phase 7 needs to branch on them yet.
export interface OtherMessage {
  type: string
  data: unknown
}

export type ServerMessage =
  | LobbyStateMessage
  | PlayerConnectionMessage
  | ActionErrorMessage
  | GameStateMessage
  | DealResultMessage
  | GameOverMessage
  | TurnTimerExpiredMessage
  | OtherMessage

export function isLobbyStateMessage(
  message: ServerMessage,
): message is LobbyStateMessage {
  return message.type === 'lobby_state'
}

export function isGameStateMessage(
  message: ServerMessage,
): message is GameStateMessage {
  return message.type === 'game_state'
}

export function isDealResultMessage(
  message: ServerMessage,
): message is DealResultMessage {
  return message.type === 'deal_result'
}

export function isGameOverMessage(
  message: ServerMessage,
): message is GameOverMessage {
  return message.type === 'game_over'
}

export function isActionErrorMessage(
  message: ServerMessage,
): message is ActionErrorMessage {
  return message.type === 'action_error'
}
