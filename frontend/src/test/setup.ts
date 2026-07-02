import '@testing-library/jest-dom/vitest'

// jsdom has no ResizeObserver (used by useFitScale); a no-op stand-in is
// enough since layout never actually changes size under jsdom
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver
