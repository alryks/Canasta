import type { PointerEvent as ReactPointerEvent } from 'react'
import { useDragStore } from '../stores/dragStore'
import type { DragOrigin } from '../stores/dragStore'

const DRAG_THRESHOLD_PX = 6

// Pointer-based drag source (plan section 13): a small movement threshold
// keeps a plain click (toggle-select) working on the same element -- only
// crossing the threshold promotes the gesture to a real drag, so this can
// be layered on top of PlayingCard's existing onClick without conflict.
// Hit-testing the drop zone under the pointer via elementFromPoint avoids
// needing every drop target to register a ref.
//
// Plain function, not a hook -- callers build one of these per card inside
// a `.map()` over a list whose length changes every render (hand size,
// meld slot count), which would break the rules of hooks if this held any
// hook-managed state itself. All per-gesture state lives in closures
// scoped to a single onPointerDown call instead.
export function makeCardDragSource(
  cardId: string,
  origin: DragOrigin,
  enabled: boolean,
  onDrop: (zone: string, cardId: string, origin: DragOrigin) => void,
) {
  function onPointerDown(event: ReactPointerEvent) {
    if (!enabled || event.button !== 0) return
    let dragging = false
    const start = { x: event.clientX, y: event.clientY }

    function onMove(moveEvent: PointerEvent) {
      const dx = moveEvent.clientX - start.x
      const dy = moveEvent.clientY - start.y
      if (!dragging) {
        if (Math.hypot(dx, dy) < DRAG_THRESHOLD_PX) return
        dragging = true
        useDragStore.getState().startDrag(cardId, origin, moveEvent.clientX, moveEvent.clientY)
      }
      const target = document.elementFromPoint(moveEvent.clientX, moveEvent.clientY)
      const zoneEl = target instanceof Element ? target.closest('[data-drop-zone]') : null
      const zone = zoneEl?.getAttribute('data-drop-zone') ?? null
      useDragStore.getState().moveDrag(moveEvent.clientX, moveEvent.clientY, zone)
    }

    function onUp() {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      if (dragging) {
        const { hoveredZone } = useDragStore.getState()
        useDragStore.getState().endDrag()
        if (hoveredZone) onDrop(hoveredZone, cardId, origin)
        const suppressDragClick = (clickEvent: MouseEvent) => {
          clickEvent.preventDefault()
          clickEvent.stopPropagation()
        }
        window.addEventListener('click', suppressDragClick, { capture: true, once: true })
        window.setTimeout(() => {
          window.removeEventListener('click', suppressDragClick, { capture: true })
        }, 0)
      }
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  return { onPointerDown }
}
