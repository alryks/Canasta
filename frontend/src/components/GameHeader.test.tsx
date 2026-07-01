import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { GameHeader } from './GameHeader'

describe('GameHeader', () => {
  it('shows both team scores against the target', () => {
    render(<GameHeader scores={{ A: 1250, B: 300 }} targetScore={5000} />)

    const scores = screen.getByRole('list', { name: 'scores' })
    expect(scores).toHaveTextContent('Команда A: 1250 / 5000')
    expect(scores).toHaveTextContent('Команда B: 300 / 5000')
  })
})
