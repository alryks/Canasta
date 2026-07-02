import { useState } from 'react'
import type { FormEvent } from 'react'
import type { ChatMessageMessage } from '../lib/protocol'

interface ChatPanelProps {
  messages: ChatMessageMessage['data'][]
  unreadCount: number
  playerNames: Record<string, string>
  onSend: (text: string) => void
  onOpen: () => void
}

// Collapsible side panel, reused as-is between GamePage and (eventually)
// LobbyPage's LobbyChat -- kept prop-driven like the rest of this codebase's
// components rather than reading useChatStore itself, so either page can
// wire it up without extra indirection.
export function ChatPanel({
  messages,
  unreadCount,
  playerNames,
  onSend,
  onOpen,
}: ChatPanelProps) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')

  function toggle() {
    setOpen((wasOpen) => {
      if (!wasOpen) onOpen()
      return !wasOpen
    })
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text) return
    onSend(text)
    setDraft('')
  }

  return (
    <div className="side-panel">
      {open && (
        <div className="side-panel-body">
          <ul aria-label="chat-messages" className="side-panel-messages">
            {messages.map((message, i) => (
              <li key={i}>
                {playerNames[message.from] ?? message.from}: {message.text}
              </li>
            ))}
          </ul>
          <form onSubmit={handleSubmit} className="side-panel-form">
            <label htmlFor="chat-input" className="visually-hidden">
              Сообщение
            </label>
            <input
              id="chat-input"
              className="input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Написать в чат…"
            />
            <button type="submit" className="btn btn-icon">
              Отправить
            </button>
          </form>
        </div>
      )}
      <button type="button" className="btn btn-primary" aria-expanded={open} onClick={toggle}>
        Чат{unreadCount > 0 ? ` (${unreadCount})` : ''}
      </button>
    </div>
  )
}
