import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DealResultModal } from './DealResultModal'

const breakdown = {
  table_points: 220,
  canasta_bonus: 500,
  hand_penalty: -25,
  three_bonus: 100,
  exit_bonus: 200,
  total: 995,
}

describe('DealResultModal', () => {
  it('shows the per-team score breakdown and running total', () => {
    render(
      <DealResultModal
        dealNumber={2}
        scoresBreakdown={{ A: breakdown }}
        teamScoresAfter={{ A: 995, B: 100 }}
        nextDeal
        onDismiss={vi.fn()}
      />,
    )

    expect(screen.getByText('Сдача №2 завершена')).toBeInTheDocument()
    const teamA = screen.getByLabelText('breakdown-A')
    expect(teamA).toHaveTextContent('Бонус за канасты: 500')
    expect(teamA).toHaveTextContent('Итого за сдачу: 995')
    expect(teamA).toHaveTextContent('Счёт партии: 995')
  })

  it('labels the dismiss button "Продолжить" when another deal follows', () => {
    render(
      <DealResultModal
        dealNumber={1}
        scoresBreakdown={{ A: breakdown }}
        teamScoresAfter={{ A: 995 }}
        nextDeal
        onDismiss={vi.fn()}
      />,
    )
    expect(screen.getByText('Продолжить')).toBeInTheDocument()
  })

  it('labels the dismiss button "Закрыть" for the final deal', () => {
    render(
      <DealResultModal
        dealNumber={1}
        scoresBreakdown={{ A: breakdown }}
        teamScoresAfter={{ A: 995 }}
        nextDeal={false}
        onDismiss={vi.fn()}
      />,
    )
    expect(screen.getByText('Закрыть')).toBeInTheDocument()
  })

  it('calls onDismiss on click', async () => {
    const onDismiss = vi.fn()
    render(
      <DealResultModal
        dealNumber={1}
        scoresBreakdown={{ A: breakdown }}
        teamScoresAfter={{ A: 995 }}
        nextDeal
        onDismiss={onDismiss}
      />,
    )

    await userEvent.click(screen.getByText('Продолжить'))
    expect(onDismiss).toHaveBeenCalled()
  })
})
