// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { arPluralRule } from '../../i18n/pluralRules'

/**
 * Pins the Arabic plural rule (#389 tail). Every `ar.json` message today
 * carries exactly two pipe segments, so only the two-way shortcut runs —
 * these tests lock that mapping and the six-way clamp that protects a
 * future three-plus-form message from silently resolving wrong.
 *
 * Pure functions, plain Node: no Nuxt context required.
 */
describe('arPluralRule', () => {
  it('maps two-segment messages one/other', () => {
    expect(arPluralRule(1, 2)).toBe(0)
    for (const n of [0, 2, 3, 11, 100]) expect(arPluralRule(n, 2)).toBe(1)
  })

  it('maps six-segment messages onto CLDR categories', () => {
    expect(arPluralRule(0, 6)).toBe(0)
    expect(arPluralRule(1, 6)).toBe(1)
    expect(arPluralRule(2, 6)).toBe(2)
    for (const n of [3, 5, 10]) expect(arPluralRule(n, 6)).toBe(3)
    for (const n of [11, 50, 99]) expect(arPluralRule(n, 6)).toBe(4)
    for (const n of [100, 1000]) expect(arPluralRule(n, 6)).toBe(5)
  })

  it('clamps short variant lists instead of overrunning', () => {
    expect(arPluralRule(100, 3)).toBeLessThanOrEqual(2)
    expect(arPluralRule(2, 2)).toBe(1)
  })
})
