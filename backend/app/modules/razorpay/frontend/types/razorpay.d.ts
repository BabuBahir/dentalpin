/**
 * Razorpay checkout.js typings (loaded from the Razorpay CDN at runtime).
 * Only the surface this module uses is declared — no `any` anywhere.
 */
export interface RazorpayCheckoutResponse {
  razorpay_payment_id: string
  razorpay_order_id: string
  razorpay_signature: string
}

export interface RazorpayOptions {
  key_id: string
  amount: number
  currency: string
  order_id: string
  name: string
  description?: string
  notes?: Record<string, string | number | null>
  handler: (response: RazorpayCheckoutResponse) => void
  /** Popup-dismissal callback (checkout.js v1 ``modal.ondismiss``). */
  modal?: { ondismiss?: () => void }
}

export interface RazorpayInstance {
  open(): void
}

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => RazorpayInstance
  }
}
