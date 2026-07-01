import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MeldDetailPopover } from './MeldDetailPopover'
import type { Meld } from '../lib/protocol'

const meld: Meld = {
  id: 'm1',
  team_id: 'B',
  kind: 'SEQUENCE',
  rank_or_suit_anchor: 'SPADES',
  slots: [
    { id: 'w1', rank: 'JOKER', suit: null },
    null,
    { id: 'c1', rank: '5', suit: 'SPADES' },
  ],
}

describe('MeldDetailPopover', () => {
  it('shows every slot, including empty ones', () => {
    render(
      <MeldDetailPopover
        meld={meld}
        canStealFrom={false}
        isStealTarget={() => false}
        onSelectStealTarget={vi.fn()}
      />,
    )

    expect(screen.getByText('JOKER')).toBeInTheDocument()
    expect(screen.getByText('5♠')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('only makes wild cards clickable when stealing is allowed', () => {
    render(
      <MeldDetailPopover
        meld={meld}
        canStealFrom={false}
        isStealTarget={() => false}
        onSelectStealTarget={vi.fn()}
      />,
    )

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('lets a wild card be selected as the steal target', async () => {
    const onSelectStealTarget = vi.fn()
    render(
      <MeldDetailPopover
        meld={meld}
        canStealFrom
        isStealTarget={() => false}
        onSelectStealTarget={onSelectStealTarget}
      />,
    )

    const wildButton = screen.getByRole('button', { name: 'JOKER' })
    expect(screen.queryByRole('button', { name: '5♠' })).not.toBeInTheDocument()

    await userEvent.click(wildButton)
    expect(onSelectStealTarget).toHaveBeenCalledWith('w1')
  })
})
