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
    <div>
      <button type="button" aria-expanded={open} onClick={toggle}>
        Чат{unreadCount > 0 ? ` (${unreadCount})` : ''}
      </button>

      {open && (
        <>
          <ul aria-label="chat-messages">
            {messages.map((message, i) => (
              <li key={i}>
                {playerNames[message.from] ?? message.from}: {message.text}
              </li>
            ))}
          </ul>
          <form onSubmit={handleSubmit}>
            <label htmlFor="chat-input">Сообщение</label>
            <input
              id="chat-input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
            <button type="submit">Отправить</button>
          </form>
        </>
      )}
    </div>
  )
}
