/**
 * Razorpay collect gateway providers (#263 / PR #373).
 *
 * Claims the ``upi`` / ``netbanking`` / ``card`` methods in the payments
 * create-payment modal so that, for an Indian clinic, clicking one of those
 * chips starts the Razorpay checkout instead of recording a manual payment.
 *
 * Boundary: talks to the payments host only through the ``useCollectGateway``
 * seam and its own public endpoints — the ``collect`` handler is exactly the
 * same trust-boundary flow the "Pagar con Razorpay" button runs (order →
 * popup → /verify), never a manual record.
 *
 * Gating lives in the provider, not the host:
 *  - ``permission: 'razorpay.collect'`` — users who can't collect online fall
 *    back to the manual record path.
 *  - ``countries: ['IN']`` — ``card`` (a primary chip everywhere) stays a
 *    manual record outside India; ``upi``/``netbanking`` chips are already
 *    IN-only in the create modal.
 */
import { registerCollectGateway } from '~~/app/composables/useCollectGateway'
import type {
  CollectGatewayParams,
  CollectGatewayResult
} from '~~/app/composables/useCollectGateway'
import { useRazorpayCheckout } from '../composables/useRazorpayCheckout'

const GATEWAY_METHODS = ['upi', 'netbanking', 'card'] as const

export default defineNuxtPlugin((nuxtApp) => {
  const t = (nuxtApp.$i18n as { t: (k: string, ...args: unknown[]) => string }).t
  const { checkoutOnce } = useRazorpayCheckout(t)

  async function collect(params: CollectGatewayParams): Promise<CollectGatewayResult> {
    return checkoutOnce(params)
  }

  for (const method of GATEWAY_METHODS) {
    registerCollectGateway({
      id: `razorpay.${method}`,
      method,
      permission: 'razorpay.collect',
      countries: ['IN'],
      collect
    })
  }
})
