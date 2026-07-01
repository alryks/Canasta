import { beforeEach, describe, expect, it } from 'vitest'
import { useEventLogStore } from './eventLogStore'

describe('useEventLogStore', () => {
  beforeEach(() => {
    useEventLogStore.getState().reset()
  })

  it('appends entries in order', () => {
    useEventLogStore.getState().addEntry('Bob подключился')
    useEventLogStore.getState().addEntry('Ход перешёл к Carol')

    const entries = useEventLogStore.getState().entries
    expect(entries.map((e) => e.text)).toEqual([
      'Bob подключился',
      'Ход перешёл к Carol',
    ])
  })

  it('caps the log at 50 entries, dropping the oldest', () => {
    for (let i = 0; i < 55; i++) {
      useEventLogStore.getState().addEntry(`event ${i}`)
    }

    const entries = useEventLogStore.getState().entries
    expect(entries).toHaveLength(50)
    expect(entries[0].text).toBe('event 5')
    expect(entries.at(-1)?.text).toBe('event 54')
  })
})
