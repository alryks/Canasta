import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createGame } from '../lib/api'
import { saveSession } from '../lib/session'

export function HomePage() {
  const navigate = useNavigate()
  const [name, setName] = useState(import.meta.env.DEV ? 'Dev Player' : '')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const devGameStarted = useRef(false)

  async function createAndOpenGame(hostName: string) {
    setError(null)
    setSubmitting(true)
    try {
      const game = await createGame(hostName)
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

  useEffect(() => {
    if (!import.meta.env.DEV || devGameStarted.current) return
    devGameStarted.current = true
    void createAndOpenGame('Dev Player')
    // This is an intentional one-shot development bootstrap.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    await createAndOpenGame(name)
  }

  return (
    <main className="page-shell">
      <div className="panel panel-narrow">
        <h1 className="brand-title">🃏 Канаста Online</h1>
        {import.meta.env.DEV && submitting && (
          <p className="status-line" role="status">
            Запускаем dev-партию с ботами…
          </p>
        )}
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="host-name">Ваше имя</label>
            <input
              id="host-name"
              className="input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              autoFocus
              placeholder="Как вас представить друзьям?"
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? 'Создаём…' : 'Создать игру'}
          </button>
        </form>
        {error && <p role="alert" className="error-text">{error}</p>}
      </div>
    </main>
  )
}
