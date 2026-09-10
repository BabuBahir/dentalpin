/**
 * Razorpay API client + collect flow for the `razorpay` module.
 *
 * The order is created server-side (the key secret never reaches the
 * browser; the API answers with the clinic's public key id). On the
 * checkout popup callback we forward the razorpay ids + signature to
 * /verify — the backend re-fetches the captured payment from Razorpay
 * and records it (amount/currency from the gateway, not from here).
 */
import type { ApiResponse, PaymentRecord } from '~~/app/types'

export interface RazorpaySettings {
  key_id: string
  is_active: boolean
  has_key_secret: boolean
}

export interface RazorpayOrder {
  order_id: string
  amount: number
  currency: string
  key_id: string
}

export interface RazorpayAllocation {
  target_type: 'budget' | 'on_account'
  target_id: string | null
  amount: number
}

export function useRazorpay() {
  const api = useApi()

  async function fetchSettings() {
    return (await api.get<ApiResponse<RazorpaySettings>>(
      '/api/v1/razorpay/settings'
    )).data
  }

  async function saveSettings(payload: {
    key_id: string
    key_secret: string
    is_active?: boolean | null
  }) {
    return (await api.put<ApiResponse<RazorpaySettings>>(
      '/api/v1/razorpay/settings',
      payload,
      { errorToast: false }
    )).data
  }

  async function createOrder(patientId: string, amount: number) {
    return (await api.post<ApiResponse<RazorpayOrder>>(
      '/api/v1/razorpay/order',
      { patient_id: patientId, amount },
      { errorToast: false }
    )).data
  }

  async function verifyAndRecord(payload: {
    patient_id: string
    payment_date: string
    razorpay_payment_id: string
    razorpay_order_id: string
    razorpay_signature: string
    allocations: RazorpayAllocation[]
  }): Promise<PaymentRecord> {
    const response = await api.post<ApiResponse<PaymentRecord>>(
      '/api/v1/razorpay/verify',
      payload,
      { errorToast: false }
    )
    return response.data
  }

  return { fetchSettings, saveSettings, createOrder, verifyAndRecord }
}

/**
 * Server-side clinic country gate — same read as the other modules
 * (`clinic.country` or the legacy `settings.country`), never a
 * client-editable field.
 */
export function useRazorpayCountry() {
  const { currentClinic } = useClinic()
  return computed(() => {
    const c = currentClinic.value as {
      country?: string | null
      settings?: { country?: string | null } | null
    } | null
    return c?.country ?? c?.settings?.country ?? null
  })
}
