/**
 * Razorpay module frontend registration.
 *
 * - `payments.collect.actions`: the "Pagar con Razorpay" button next to
 *   each collect CTA. Visible only when the clinic's server-side country
 *   is India (`IN`); the component also requires a resolvable patient.
 * - Settings form under Settings → Integrations for the per-clinic
 *   gateway credentials.
 *
 * Boundary: this module talks to the payments host only via the slot name
 * and its own public endpoints — never modules' internals.
 */
import { registerSlot } from '~~/app/composables/useModuleSlots'
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSlot('payments.collect.actions', {
    id: 'razorpay.collect.actions',
    component: defineAsyncComponent(() => import('../components/RazorpayCollectButton.vue')),
    permission: 'razorpay.collect',
    order: 10
  })

  registerSettingsPage({
    path: 'razorpay',
    category: 'integrations',
    labelKey: 'razorpay.settings.title',
    descriptionKey: 'razorpay.settings.description',
    icon: 'i-lucide-indian-rupee',
    permission: 'razorpay.settings.read',
    component: () => import('../components/RazorpaySettingsPage.vue'),
    searchKeywords: ['razorpay', 'upi', 'netbanking', 'pago online', 'payment gateway'],
    order: 52
  })
})
