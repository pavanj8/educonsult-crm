import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Node 22+ ships an experimental built-in Web Storage that shadows the one
// jsdom installs, and it resolves to undefined unless the process was started
// with --localstorage-file. CI runs Node 24, where jsdom's implementation wins,
// so this only bites local runs on newer Node -- but there it fails every test
// that touches localStorage. The guard makes it a no-op wherever a real
// implementation is already present.
if (!globalThis.localStorage) {
  const store = new Map<string, string>()
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
      setItem: (key: string, value: string) => void store.set(key, String(value)),
      removeItem: (key: string) => void store.delete(key),
      clear: () => store.clear(),
      key: (index: number) => Array.from(store.keys())[index] ?? null,
      get length() {
        return store.size
      },
    },
  })
}

afterEach(() => {
  cleanup()
})
