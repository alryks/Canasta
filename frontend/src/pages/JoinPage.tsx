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
    <main className="page-shell">
      <div className="panel panel-narrow">
        <h1 className="brand-title">Присоединиться к игре</h1>
        <p className="brand-subtitle">Введите имя, чтобы сесть за стол</p>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="join-name">Ваше имя</label>
            <input
              id="join-name"
              className="input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              autoFocus
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? 'Входим…' : 'Войти'}
          </button>
        </form>
        {error && <p role="alert" className="error-text">{error}</p>}
      </div>
    </main>
  )
}
