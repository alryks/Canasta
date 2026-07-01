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

// game_state and everything past it (deal_result, game_over, ...) is fleshed
// out once the game board lands in phase 7 -- the lobby only needs to know
// that a non-lobby message means "the game has started".
export interface OtherMessage {
  type: string
  data: unknown
}

export type ServerMessage =
  | LobbyStateMessage
  | PlayerConnectionMessage
  | ActionErrorMessage
  | OtherMessage

export function isLobbyStateMessage(
  message: ServerMessage,
): message is LobbyStateMessage {
  return message.type === 'lobby_state'
}
