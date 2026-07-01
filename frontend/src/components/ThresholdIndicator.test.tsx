import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ThresholdIndicator } from './ThresholdIndicator'

describe('ThresholdIndicator', () => {
  it('shows progress while the team is not yet opened', () => {
    render(<ThresholdIndicator teamId="A" accumulated={15} threshold={30} />)
    expect(screen.getByText(/15\/30/)).toBeInTheDocument()
  })

  it('hides once accumulated points reach the threshold', () => {
    render(<ThresholdIndicator teamId="A" accumulated={30} threshold={30} />)
    expect(screen.queryByLabelText('threshold-A')).not.toBeInTheDocument()
  })

  it('stays hidden past the threshold too', () => {
    render(<ThresholdIndicator teamId="A" accumulated={45} threshold={30} />)
    expect(screen.queryByLabelText('threshold-A')).not.toBeInTheDocument()
  })
})
