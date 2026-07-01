import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { joinGame } from '../lib/api'
import { saveSession } from '../lib/session'

export function JoinPage() {
  const { gameId = '' } = useParams()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const joined = await joinGame(gameId, name)
      saveSession(gameId, {
        playerId: joined.player_id,
        sessionToken: joined.session_token,
      })
      navigate(`/games/${gameId}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'не удалось присоединиться')
      setSubmitting(false)
    }
  }

  return (
    <main>
      <h1>Присоединиться к игре</h1>
      <form onSubmit={handleSubmit}>
        <label htmlFor="join-name">Ваше имя</label>
        <input
          id="join-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
        />
        <button type="submit" disabled={submitting}>
          Войти
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
    </main>
  )
}
