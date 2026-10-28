// Shared Vitest setup for jsdom tests.
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// Monaco loads from a CDN in the browser; stub it so tests stay offline & fast.
vi.mock('@monaco-editor/react', async () => {
  const React = await import('react')
  return {
    default: (props: { value?: string; language?: string }) =>
      React.createElement(
        'pre',
        { 'data-testid': 'monaco-stub', 'data-language': props.language ?? '' },
        props.value ?? '',
      ),
    loader: {
      config: vi.fn(),
      init: vi.fn(() => Promise.resolve({})),
    },
  }
})

// jsdom does not implement these browser APIs.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia
}

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

if (!('clipboard' in navigator) || !navigator.clipboard) {
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  window.sessionStorage.clear()
  window.localStorage.clear()
})
