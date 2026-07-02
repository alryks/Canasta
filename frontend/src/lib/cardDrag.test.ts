import type { PointerEvent as ReactPointerEvent } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { makeCardDragSource } from './cardDrag'
import { useDragStore } from '../stores/dragStore'

function fakePointerDown(x: number, y: number): ReactPointerEvent {
  return { button: 0, clientX: x, clientY: y } as ReactPointerEvent
}

function firePointerMove(x: number, y: number) {
  window.dispatchEvent(new PointerEvent('pointermove', { clientX: x, clientY: y }))
}

function firePointerUp() {
  window.dispatchEvent(new PointerEvent('pointerup'))
}

describe('makeCardDragSource', () => {
  beforeEach(() => {
    useDragStore.getState().endDrag()
    vi.restoreAllMocks()
  })

  it('does nothing when disabled', () => {
    const onDrop = vi.fn()
    const { onPointerDown } = makeCardDragSource('c1', 'hand', false, onDrop)
    onPointerDown(fakePointerDown(0, 0))
    firePointerMove(50, 50)
    firePointerUp()

    expect(useDragStore.getState().cardId).toBeNull()
    expect(onDrop).not.toHaveBeenCalled()
  })

  it('ignores tiny movements (lets a plain click through) and never calls onDrop', () => {
    const onDrop = vi.fn()
    const { onPointerDown } = makeCardDragSource('c1', 'hand', true, onDrop)
    onPointerDown(fakePointerDown(100, 100))
    firePointerMove(102, 101)
    firePointerUp()

    expect(useDragStore.getState().cardId).toBeNull()
    expect(onDrop).not.toHaveBeenCalled()
  })

  it('starts a drag once movement crosses the threshold and tracks the hovered zone', () => {
    const zoneEl = document.createElement('div')
    zoneEl.setAttribute('data-drop-zone', 'discard')
    document.body.appendChild(zoneEl)
    document.elementFromPoint = vi.fn().mockReturnValue(zoneEl)

    const onDrop = vi.fn()
    const { onPointerDown } = makeCardDragSource('c1', 'hand', true, onDrop)
    onPointerDown(fakePointerDown(0, 0))
    firePointerMove(40, 0)

    expect(useDragStore.getState().cardId).toBe('c1')
    expect(useDragStore.getState().hoveredZone).toBe('discard')

    firePointerUp()
    expect(onDrop).toHaveBeenCalledWith('discard', 'c1', 'hand')
    expect(useDragStore.getState().cardId).toBeNull()

    zoneEl.remove()
  })

  it('drops nothing and resets the store when released outside any zone', () => {
    document.elementFromPoint = vi.fn().mockReturnValue(null)
    const onDrop = vi.fn()
    const { onPointerDown } = makeCardDragSource('c1', 'hand', true, onDrop)
    onPointerDown(fakePointerDown(0, 0))
    firePointerMove(40, 0)
    firePointerUp()

    expect(onDrop).not.toHaveBeenCalled()
    expect(useDragStore.getState().cardId).toBeNull()
  })
})
