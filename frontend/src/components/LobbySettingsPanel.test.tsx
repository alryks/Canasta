import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { LobbySettingsPanel } from './LobbySettingsPanel'

// the real target_score field is a controlled input mirroring server state --
// a static prop would make typing "3000" append onto "5000" instead of
// replacing it, so this stands in for the parent that re-renders with the
// server's echoed value after each change.
function ControlledPanel({ onChange }: { onChange: (score: number) => void }) {
  const [targetScore, setTargetScore] = useState(5000)
  return (
    <LobbySettingsPanel
      targetScore={targetScore}
      discardVisibility="TOP_ONLY"
      isHost
      onChange={(change) => {
        if (change.target_score !== undefined) {
          setTargetScore(change.target_score)
          onChange(change.target_score)
        }
      }}
    />
  )
}

describe('LobbySettingsPanel', () => {
  it('shows read-only settings for non-host viewers', () => {
    render(
      <LobbySettingsPanel
        targetScore={5000}
        discardVisibility="TOP_ONLY"
        isHost={false}
        onChange={vi.fn()}
      />,
    )

    expect(screen.getByText(/5000/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Целевой счёт')).not.toBeInTheDocument()
  })

  it('lets the host edit the target score', async () => {
    const onChange = vi.fn()
    render(<ControlledPanel onChange={onChange} />)

    const input = screen.getByLabelText('Целевой счёт')
    await userEvent.clear(input)
    await userEvent.type(input, '3000')

    expect(onChange).toHaveBeenLastCalledWith(3000)
  })

  it('lets the host change discard visibility', async () => {
    const onChange = vi.fn()
    render(
      <LobbySettingsPanel
        targetScore={5000}
        discardVisibility="TOP_ONLY"
        isHost
        onChange={onChange}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Вся стопка' }))

    expect(onChange).toHaveBeenCalledWith({ discard_visibility: 'FULL' })
  })
})
