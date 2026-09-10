/**
 * Razorpay checkout runner — shared by the "Pagar con Razorpay" slot button
 * and the create-payment gateway providers (UPI / netbanking / card chips).
 *
 * Owns the whole client half of the collect flow:
 *   1. load checkout.js from the CDN,
 *   2. POST /order (server-side, returns the clinic's public key id),
 *   3. open the Razorpay popup,
 *   4. forward the callback ids + signature to POST /verify.
 *
 * Returns a settled outcome so hosts can branch:
 *   - ``{ ok: true, payment }``          → captured + recorded (/verify)
 *   - ``{ ok: false, 'unconfigured' }``  → clinic has no usable gateway keys
 *   - ``{ ok: false, 'cancelled' }``     → popup dismissed without paying
 *   - ``{ ok: false, 'error', error }``  → order/verify failed
 *
 * Security mirror of the backend contract: amount/currency/method are never
 * decided here — /verify only receives ids + signature + allocation targets
 * (their sum is re-checked against the captured amount server-side).
 */
import type { PaymentAllocationCreate, PaymentRecord } from '~~/app/types'
import { errorDetail, errorStatus } from '~~/app/utils/error'
import type { RazorpayCheckoutResponse } from '../types/razorpay'

export type RazorpayCheckoutOutcome
  = | { ok: true, payment: PaymentRecord }
    | { ok: false, reason: 'unconfigured' | 'cancelled' | 'error', error?: string }

export interface RazorpayCheckoutParams {
  patient_id: string
  amount: number
  payment_date: string
  allocations: PaymentAllocationCreate[]
}

/**
 * Translator used for collect-flow user-facing strings. When invoked from a
 * component setup, ``useI18n().t`` is used; hosts without a Vue component
 * instance (Nuxt plugins) must pass ``nuxtApp.$i18n.t`` instead.
 */
export type RazorpayCheckoutT = (key: string, ...args: unknown[]) => string

export function useRazorpayCheckout(t?: RazorpayCheckoutT) {
  const translate = t ?? useI18n().t
  const { createOrder, verifyAndRecord } = useRazorpay(t)

  function loadRazorpayScript(): Promise<boolean> {
    return new Promise((resolve) => {
      if (window.Razorpay) {
        resolve(true)
        return
      }
      const script = document.createElement('script')
      script.src = 'https://checkout.razorpay.com/v1/checkout.js'
      script.onload = () => resolve(true)
      script.onerror = () => resolve(false)
      document.head.appendChild(script)
    })
  }

  async function checkoutOnce(params: RazorpayCheckoutParams): Promise<RazorpayCheckoutOutcome> {
    const loaded = await loadRazorpayScript()
    if (!loaded) {
      return { ok: false, reason: 'error', error: translate('razorpay.collect.loadError') }
    }

    let order
    try {
      order = await createOrder(params.patient_id, params.amount)
    } catch (e) {
      // /order returns 400 exactly when the clinic has no usable gateway
      // credentials (RazorpayNotConfiguredError → HTTP 400). Hosts use this
      // signal to fall back to a manual record.
      if (errorStatus(e) === 400) {
        return { ok: false, reason: 'unconfigured', error: errorDetail(e) }
      }
      return { ok: false, reason: 'error', error: errorDetail(e) ?? translate('razorpay.collect.error') }
    }

    const RazorpayCtor = window.Razorpay
    if (!RazorpayCtor) {
      return { ok: false, reason: 'error', error: translate('razorpay.collect.loadError') }
    }

    return new Promise<RazorpayCheckoutOutcome>((resolve) => {
      const rzp = new RazorpayCtor({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        order_id: order.order_id,
        name: 'DentalPin',
        description: translate('razorpay.collect.description'),
        handler: async (response: RazorpayCheckoutResponse) => {
          try {
            const payment = await verifyAndRecord({
              patient_id: params.patient_id,
              payment_date: params.payment_date,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_order_id: response.razorpay_order_id,
              razorpay_signature: response.razorpay_signature,
              // PaymentAllocationCreate allows `target_id?: string`; the
              // gateway payload carries an explicit `null` for on-account.
              allocations: params.allocations.map(a => ({
                target_type: a.target_type,
                target_id: a.target_id ?? null,
                amount: a.amount
              }))
            })
            resolve({ ok: true, payment })
          } catch (e) {
            resolve({ ok: false, reason: 'error', error: errorDetail(e) ?? translate('razorpay.collect.verifyError') })
          }
        },
        modal: {
          ondismiss: () => resolve({ ok: false, reason: 'cancelled' })
        }
      })
      rzp.open()
    })
  }

  return { checkoutOnce }
}
