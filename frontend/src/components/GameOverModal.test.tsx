import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { GameOverModal } from './GameOverModal'

describe('GameOverModal', () => {
  it('announces the winning team and final scores', () => {
    render(<GameOverModal winnerTeamId="A" finalScores={{ A: 5200, B: 3100 }} />)

    expect(screen.getByText(/Победила команда A/)).toBeInTheDocument()
    const scores = screen.getByLabelText('final-scores')
    expect(scores).toHaveTextContent('Команда A: 5200')
    expect(scores).toHaveTextContent('Команда B: 3100')
  })
})
