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
    <div className="table-tool">
      {open && (
        <div className="modal-overlay" role="dialog" aria-label="chat-modal">
          <div className="panel modal-panel chat-modal">
            <div className="modal-header">
              <h3>Чат</h3>
              <button type="button" className="modal-close-btn" onClick={toggle} aria-label="Закрыть">
                ×
              </button>
            </div>
            <ul aria-label="chat-messages" className="modal-messages">
              {messages.map((message, i) => (
                <li key={i}>
                  <span className="message-author">{playerNames[message.from] ?? message.from}</span>
                  <span className="message-text">{message.text}</span>
                </li>
              ))}
            </ul>
            <form onSubmit={handleSubmit} className="modal-message-form">
              <label htmlFor="chat-input" className="visually-hidden">
                Сообщение
              </label>
              <input
                id="chat-input"
                className="input"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Сообщение"
              />
              <button type="submit" className="btn btn-primary">
                Отправить
              </button>
            </form>
          </div>
        </div>
      )}
      <button
        type="button"
        className={`btn btn-primary table-tool-btn${unreadCount > 0 ? ' has-unread' : ''}`}
        aria-expanded={open}
        onClick={toggle}
      >
        Чат
        {unreadCount > 0 && <span className="unread-badge">{unreadCount}</span>}
      </button>
    </div>
  )
}
