import { describe, expect, it } from 'vitest'
import { meldCardOverlapPx } from './meldLayout'

describe('meldCardOverlapPx', () => {
  it('returns zero for a single card', () => {
    expect(meldCardOverlapPx(1)).toBe(0)
  })

  it('uses tighter overlap as melds grow longer', () => {
    expect(meldCardOverlapPx(7)).toBeGreaterThan(meldCardOverlapPx(3))
  })
})
