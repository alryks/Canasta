import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createGame } from '../lib/api'
import { saveSession } from '../lib/session'

export function HomePage() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const game = await createGame(name)
      saveSession(game.game_id, {
        playerId: game.player_id,
        sessionToken: game.host_session_token,
      })
      navigate(`/games/${game.game_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'не удалось создать игру')
      setSubmitting(false)
    }
  }

  return (
    <main>
      <h1>Канаста Online</h1>
      <form onSubmit={handleSubmit}>
        <label htmlFor="host-name">Ваше имя</label>
        <input
          id="host-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
        />
        <button type="submit" disabled={submitting}>
          Создать игру
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
    </main>
  )
}
