import { describe, expect, it, beforeEach } from 'vitest'
import type { PaymentMethod } from '~~/app/types'
import type { CollectGatewayProvider, CollectGatewayResult } from '~~/app/composables/useCollectGateway'

// useCollectGateway is the seam that lets gateway modules (razorpay) claim
// a payment method so the create-payment modal delegates to their checkout
// instead of recording manually. The registry must satisfy the same rules
// as useModuleSlots: idempotent re-registration (HMR), a permission gate the
// module sets, and a per-country gate so a global gateway (e.g. `card` via
// razorpay) stays out of clinics it does not serve.

function provider(method: PaymentMethod, overrides: Partial<CollectGatewayProvider> = {}): CollectGatewayProvider {
  return {
    id: `test.${method}`,
    method,
    countries: ['IN'],
    collect: async (_params): Promise<CollectGatewayResult> => ({ ok: false, reason: 'cancelled' }),
    ...overrides
  }
}

describe('useCollectGateway', () => {
  beforeEach(async () => {
    const { clearCollectGateways } = await import('~~/app/composables/useCollectGateway')
    clearCollectGateways()
  })

  it('resolves the provider for a registered method', async () => {
    const { registerCollectGateway, resolveCollectGateway }
      = await import('~~/app/composables/useCollectGateway')

    registerCollectGateway(provider('upi'))

    const resolved = resolveCollectGateway('upi', { can: () => true, country: 'IN' })
    expect(resolved?.id).toBe('test.upi')
    expect(resolveCollectGateway('cash', { can: () => true, country: 'IN' })).toBeUndefined()
  })

  it('re-registering the same id replaces the entry (HMR idempotent)', async () => {
    const { registerCollectGateway, resolveCollectGateway }
      = await import('~~/app/composables/useCollectGateway')

    registerCollectGateway(provider('upi'))
    registerCollectGateway(provider('upi', { id: 'test.upi', permission: 'razorpay.collect' }))

    const resolved = resolveCollectGateway('upi', { can: () => true, country: 'IN' })
    expect(resolved?.id).toBe('test.upi')
    expect(resolved?.permission).toBe('razorpay.collect')
  })

  it('filters by the provider permission gate', async () => {
    const { registerCollectGateway, resolveCollectGateway }
      = await import('~~/app/composables/useCollectGateway')

    registerCollectGateway(provider('netbanking', { permission: 'razorpay.collect' }))

    expect(resolveCollectGateway('netbanking', { can: () => true, country: 'IN' })?.id).toBe('test.netbanking')
    expect(resolveCollectGateway('netbanking', { can: () => false, country: 'IN' })).toBeUndefined()
  })

  it('filters by the clinic country when the provider declares countries', async () => {
    const { registerCollectGateway, resolveCollectGateway }
      = await import('~~/app/composables/useCollectGateway')

    // `card` is gateway-backed only in India; elsewhere it must fall back
    // to the manual record path.
    registerCollectGateway(provider('card', { id: 'razorpay.card' }))

    expect(resolveCollectGateway('card', { can: () => true, country: 'IN' })?.id).toBe('razorpay.card')
    expect(resolveCollectGateway('card', { can: () => true, country: 'US' })).toBeUndefined()
    expect(resolveCollectGateway('card', { can: () => true, country: null })).toBeUndefined()
  })

  it('unregisters a provider by id', async () => {
    const { registerCollectGateway, unregisterCollectGateway, resolveCollectGateway }
      = await import('~~/app/composables/useCollectGateway')

    registerCollectGateway(provider('upi'))
    registerCollectGateway(provider('netbanking'))

    unregisterCollectGateway('test.upi')

    expect(resolveCollectGateway('upi', { can: () => true, country: 'IN' })).toBeUndefined()
    expect(resolveCollectGateway('netbanking', { can: () => true, country: 'IN' })).toBeDefined()
  })
})
