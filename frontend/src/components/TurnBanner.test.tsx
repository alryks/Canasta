import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { TurnBanner } from './TurnBanner'

describe('TurnBanner', () => {
  it("labels the viewer's own turn", () => {
    render(
      <TurnBanner
        turnPlayerId="p1"
        viewerId="p1"
        turnPhase="ACT"
        playerNames={{ p1: 'Alice' }}
      />,
    )

    expect(screen.getByText(/Ваш ход/)).toBeInTheDocument()
    expect(screen.getByText(/выкладывает\/сбрасывает/)).toBeInTheDocument()
  })

  it("names the other player and phase", () => {
    render(
      <TurnBanner
        turnPlayerId="p1"
        viewerId="p2"
        turnPhase="DRAW"
        playerNames={{ p1: 'Alice', p2: 'Bob' }}
      />,
    )

    expect(screen.getByText(/Ходит Alice/)).toBeInTheDocument()
    expect(screen.getByText(/берёт карту/)).toBeInTheDocument()
  })
})
