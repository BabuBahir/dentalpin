/**
 * Payment-gateway provider seam (#263 / #365 / PR #373).
 *
 * The payments create-payment modal renders a fixed chip list of methods;
 * a *gateway* module (razorpay) wants a chip (e.g. ``upi``) to launch its
 * checkout instead of recording a manual payment. This registry lets a
 * provider register a ``collect`` handler per payment method; the modal
 * calls ``resolveCollectGateway(method)`` before submitting and delegates
 * to the handler when a provider matches — otherwise it keeps the manual
 * record path.
 *
 * Lifetime + SSR: providers are registered from each gateway module's
 * ``*.client.ts`` plugin, so no browser API runs on the server and the
 * registry is empty until a gateway module is installed. Lookup happens
 * only at submit time (client-side).
 *
 * Boundary rules (ADR 0003 / module contract):
 *  - The host (payments) never imports the gateway module — it resolves
 *    purely by ``PaymentMethod`` string plus the provider's own
 *    ``permission`` / ``countries`` gates.
 *  - The provider never imports payments internals: it receives
 *    ``CollectGatewayParams`` and returns a settled ``CollectGatewayResult``.
 *
 * Mirrors ``useModuleSlots``: plain functions over a ``useState``-backed map
 * (SSR + HMR safe) and a composable wrapper that injects ``can``/country at
 * call time.
 */

import type {
  PaymentAllocationCreate,
  PaymentMethod,
  PaymentRecord
} from '~/types'

export type CollectGatewayReason = 'unconfigured' | 'cancelled' | 'error'

export type CollectGatewayResult
  = | { ok: true, payment: PaymentRecord }
    | { ok: false, reason: CollectGatewayReason, error?: string }

export interface CollectGatewayParams {
  patient_id: string
  amount: number
  payment_date: string
  allocations: PaymentAllocationCreate[]
}

export interface CollectGatewayProvider {
  /**
   * Stable identifier, deduped on re-registration. ``<module>.<method>``.
   */
  id: string
  /** Payment method this provider claims (e.g. ``'upi'``). */
  method: PaymentMethod
  /** Namespaced permission; the provider is ignored when the user can't. */
  permission?: string
  /**
   * ISO alpha-2 country codes the gateway serves (e.g. ``['IN']``).
   * Empty/undefined = every country. Keeps gateway providers (e.g. card
   * via razorpay) out of clinics where the gateway must not run.
   */
  countries?: string[]
  /** Run the gateway flow. Never throws — always settles. */
  collect: (params: CollectGatewayParams) => Promise<CollectGatewayResult>
}

// Keyed by PaymentMethod string. A plain string-keyed record keeps the
// registry open to methods added later and lets `{}` be a valid empty state.
type GatewayMap = Record<string, CollectGatewayProvider[]>

function useGatewayState() {
  return useState<GatewayMap>('payments:collect:gateways', () => ({}))
}

export function registerCollectGateway(provider: CollectGatewayProvider): void {
  const state = useGatewayState()
  const bucket = state.value[provider.method] || []
  // Replace a previously registered provider with the same id — HMR / reload
  // idempotent, same convention as useModuleSlots.
  const deduped = bucket.filter(e => e.id !== provider.id)
  state.value = {
    ...state.value,
    [provider.method]: [...deduped, provider]
  }
}

export function unregisterCollectGateway(id: string): void {
  const state = useGatewayState()
  const next: GatewayMap = {}
  for (const [method, bucket] of Object.entries(state.value)) {
    const remaining = bucket.filter(e => e.id !== id)
    if (remaining.length > 0) next[method] = remaining
  }
  state.value = next
}

export function clearCollectGateways(): void {
  useGatewayState().value = {}
}

/**
 * Resolve the first provider for ``method`` that passes its own gates.
 * Providers that declare a ``permission`` require ``ctx.can(...)``; those
 * that declare ``countries`` require the current clinic country to match.
 */
export function resolveCollectGateway(
  method: PaymentMethod,
  ctx: { can: (permission: string) => boolean, country: string | null }
): CollectGatewayProvider | undefined {
  return (useGatewayState().value[method] || []).find((entry) => {
    if (entry.permission && !ctx.can(entry.permission)) return false
    if (entry.countries?.length && !entry.countries.includes(ctx.country ?? '')) return false
    return true
  })
}

/**
 * Composable wrapper. ``useCollectGateway().resolve(method)`` is what the
 * create-payment modal calls — it injects the caller's permission set and
 * the server-side clinic country so the modal host stays gateway-agnostic.
 */
export function useCollectGateway() {
  const { can } = usePermissions()
  const clinicCountry = useClinicCountry()

  function resolve(method: PaymentMethod): CollectGatewayProvider | undefined {
    return resolveCollectGateway(method, {
      can,
      country: clinicCountry.value
    })
  }

  return {
    register: registerCollectGateway,
    unregister: unregisterCollectGateway,
    clear: clearCollectGateways,
    resolve
  }
}
