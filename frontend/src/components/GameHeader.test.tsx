import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { GameHeader } from './GameHeader'

describe('GameHeader', () => {
  it('shows both team scores against the target', () => {
    render(
      <GameHeader
        scores={{ A: 1250, B: 300 }}
        targetScore={5000}
        turnPlayerId="p1"
        turnPhase="DRAW"
        viewerId="p2"
        playerNames={{ p1: 'Alice', p2: 'Bob' }}
      />,
    )

    const scores = screen.getByRole('list', { name: 'scores' })
    expect(scores).toHaveTextContent('Команда A: 1250 / 5000')
    expect(scores).toHaveTextContent('Команда B: 300 / 5000')
  })

  it("labels the current player's own turn", () => {
    render(
      <GameHeader
        scores={{ A: 0, B: 0 }}
        targetScore={5000}
        turnPlayerId="p1"
        turnPhase="ACT"
        viewerId="p1"
        playerNames={{ p1: 'Alice' }}
      />,
    )

    expect(screen.getByText(/Ваш ход/)).toBeInTheDocument()
  })

  it("names the other player whose turn it is", () => {
    render(
      <GameHeader
        scores={{ A: 0, B: 0 }}
        targetScore={5000}
        turnPlayerId="p1"
        turnPhase="DRAW"
        viewerId="p2"
        playerNames={{ p1: 'Alice', p2: 'Bob' }}
      />,
    )

    expect(screen.getByText(/Ходит Alice/)).toBeInTheDocument()
  })
})
