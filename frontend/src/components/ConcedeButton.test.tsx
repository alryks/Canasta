import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ConcedeButton } from './ConcedeButton'

describe('ConcedeButton', () => {
  it('renders nothing when not visible', () => {
    render(<ConcedeButton visible={false} onConcede={vi.fn()} />)
    expect(screen.queryByText(/Штраф −1000/)).not.toBeInTheDocument()
  })

  it('requires a confirming second click before conceding', async () => {
    const onConcede = vi.fn()
    render(<ConcedeButton visible onConcede={onConcede} />)

    await userEvent.click(screen.getByText(/Штраф −1000/))
    expect(onConcede).not.toHaveBeenCalled()

    await userEvent.click(screen.getByText(/Подтвердить/))
    expect(onConcede).toHaveBeenCalledTimes(1)
  })
})
