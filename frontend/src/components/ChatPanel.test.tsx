import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ChatPanel } from './ChatPanel'

const messages = [
  { from: 'p1', text: 'hi all', ts: '2026-01-01T00:00:00Z' },
  { from: 'p2', text: 'hey', ts: '2026-01-01T00:00:01Z' },
]

describe('ChatPanel', () => {
  it('shows the unread count while collapsed', () => {
    render(
      <ChatPanel
        messages={[]}
        unreadCount={3}
        playerNames={{}}
        onSend={vi.fn()}
        onOpen={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: /Чат/ })).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('reveals messages with player names and marks them read on open', async () => {
    const onOpen = vi.fn()
    render(
      <ChatPanel
        messages={messages}
        unreadCount={2}
        playerNames={{ p1: 'Alice', p2: 'Bob' }}
        onSend={vi.fn()}
        onOpen={onOpen}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: /Чат/ }))

    expect(onOpen).toHaveBeenCalled()
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('hi all')).toBeInTheDocument()
    expect(screen.getByText('Bob')).toBeInTheDocument()
    expect(screen.getByText('hey')).toBeInTheDocument()
  })

  it('sends the typed message and clears the input', async () => {
    const onSend = vi.fn()
    render(
      <ChatPanel
        messages={[]}
        unreadCount={0}
        playerNames={{}}
        onSend={onSend}
        onOpen={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: /Чат/ }))
    const input = screen.getByLabelText('Сообщение')
    await userEvent.type(input, 'hello there')
    await userEvent.click(screen.getByText('Отправить'))

    expect(onSend).toHaveBeenCalledWith('hello there')
    expect(input).toHaveValue('')
  })

  it('does not send a blank message', async () => {
    const onSend = vi.fn()
    render(
      <ChatPanel
        messages={[]}
        unreadCount={0}
        playerNames={{}}
        onSend={onSend}
        onOpen={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: /Чат/ }))
    await userEvent.click(screen.getByText('Отправить'))

    expect(onSend).not.toHaveBeenCalled()
  })
})
