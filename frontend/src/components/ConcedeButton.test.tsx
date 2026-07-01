import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ConcedeButton } from './ConcedeButton'

describe('ConcedeButton', () => {
  it('renders nothing when not visible', () => {
    render(<ConcedeButton visible={false} onConcede={vi.fn()} />)
    expect(screen.queryByText('Не могу выложить')).not.toBeInTheDocument()
  })

  it('sends concede_penalty on click when visible', async () => {
    const onConcede = vi.fn()
    render(<ConcedeButton visible onConcede={onConcede} />)

    await userEvent.click(screen.getByText('Не могу выложить'))
    expect(onConcede).toHaveBeenCalled()
  })
})
