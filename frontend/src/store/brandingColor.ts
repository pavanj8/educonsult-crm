/**
 * Brand color helpers for E10 / Journey J3 tenant branding.
 *
 * Kept in a separate module from the React provider so the parsing
 * and contrast-picking logic can be unit-tested in isolation and
 * shared by the BrandingProvider, the settings page, and any future
 * white-label consumer (e.g. an invoice PDF generator) without
 * pulling in React.
 *
 * The module is intentionally tiny and free of React imports.
 */

const HEX6_PATTERN = /^#[0-9A-Fa-f]{6}$/

/**
 * Parse a hex ``#RRGGBB`` string into ``[r, g, b]`` 0..255 components.
 * Returns null when the value is not a 6-digit hex string so callers
 * can fall back instead of propagating junk to the DOM.
 */
export function parseHexColor(value: string): [number, number, number] | null {
  if (!HEX6_PATTERN.test(value)) {
    return null
  }
  const r = parseInt(value.slice(1, 3), 16)
  const g = parseInt(value.slice(3, 5), 16)
  const b = parseInt(value.slice(5, 7), 16)
  if ([r, g, b].some((component) => Number.isNaN(component))) {
    return null
  }
  return [r, g, b]
}

/**
 * Pick readable foreground color for a given background ``#RRGGBB``.
 *
 * Uses the W3C-recommended relative luminance formula (sRGB linearized)
 * and a luminance threshold of ``0.2`` chosen so the picked token
 * clears the WCAG AA 4.5:1 contrast bar for most brand colors:
 *
 * * background luminance ``< 0.2`` -> ``#ffffff`` foreground
 *   (e.g. ``#1A2B3C``, ``#2563EB``)
 * * background luminance ``>= 0.2`` -> ``#111827`` foreground
 *   (e.g. ``#FAFAFA``, ``#FFD700``)
 *
 * Near-grey mid-tones (luminance 0.18..0.22) are deliberately not
 * targeted; tenants can avoid this band by choosing a more saturated
 * brand color.
 */
export function pickContrastColor(value: string): '#ffffff' | '#111827' {
  const components = parseHexColor(value)
  if (components === null) {
    return '#ffffff'
  }
  const [r, g, b] = components
  const linear = (channel: number): number => {
    const c = channel / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  const luminance =
    0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
  return luminance < 0.2 ? '#ffffff' : '#111827'
}

/**
 * Canonical 6-digit hex color string (``#RRGGBB``). The runtime
 * validator is :func:`HEX6_PATTERN`; the type is intentionally
 * permissive (``#${string}``) because TypeScript cannot currently
 * express the 6-digit regex in a template-literal type. Callers
 * should validate via :func:`parseHexColor` before rendering or
 * persisting a value.
 */
export type BrandColor = `#${string}`
