// REST client for the lobby endpoints (plan section 11) -- everything
// before the WS socket opens.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export interface CreateGameResponse {
  game_id: string
  invite_link: string
  host_session_token: string
  player_id: string
}

export interface JoinGameResponse {
  player_id: string
  session_token: string
}

export interface PlayerPublic {
  id: string
  name: string
  seat: number | null
  team_id: string | null
  connected: boolean
  is_host: boolean
}

export interface LobbyStateResponse {
  game_id: string
  status: string
  host_id: string
  target_score: number
  discard_visibility: string
  players: PlayerPublic[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function createGame(hostName: string): Promise<CreateGameResponse> {
  return request('/games', {
    method: 'POST',
    body: JSON.stringify({ host_name: hostName }),
  })
}

export function joinGame(gameId: string, name: string): Promise<JoinGameResponse> {
  return request(`/games/${gameId}/join`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export function getLobby(gameId: string): Promise<LobbyStateResponse> {
  return request(`/games/${gameId}/lobby`)
}

export function wsUrl(gameId: string, token: string): string {
  const wsBase = API_BASE_URL.replace(/^http/, 'ws')
  return `${wsBase}/ws/games/${gameId}?token=${encodeURIComponent(token)}`
}
