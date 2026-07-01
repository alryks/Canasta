import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { EventLog } from './EventLog'

const entries = [
  { id: 'e1', text: 'Bob подключился' },
  { id: 'e2', text: 'Сдача №1 завершена' },
]

describe('EventLog', () => {
  it('shows the entry count while collapsed, hiding the list', () => {
    render(<EventLog entries={entries} />)

    expect(screen.getByText('Лента событий (2)')).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('reveals every entry on click', async () => {
    render(<EventLog entries={entries} />)

    await userEvent.click(screen.getByText('Лента событий (2)'))

    expect(screen.getByText('Bob подключился')).toBeInTheDocument()
    expect(screen.getByText('Сдача №1 завершена')).toBeInTheDocument()
  })
})
