import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

interface ClinicCtx {
  clinic?: { country?: string | null, settings?: { country?: string | null } | null } | null
}

// Same country-gating pattern india_gst/verifactu already use: read
// from the server-authoritative clinic object, never a client-editable
// field. Razorpay UPI/QR/payment-link collection only makes sense for
// India clinics — everything else (non-India) sees nothing from this
// module at all.
function isIndiaClinicCtx(raw: unknown): boolean {
  const ctx = (raw ?? {}) as ClinicCtx
  const country = ctx.clinic?.country ?? ctx.clinic?.settings?.country ?? null
  return country === 'IN'
}

export default defineNuxtPlugin(() => {
  registerSlot('settings.sections', {
    id: 'razorpay.settings.cards',
    component: defineAsyncComponent(() => import('../components/RazorpaySettingsCardsSlot.vue')),
    order: 62,
    category: 'billing',
    labelKey: 'razorpay.settingsCards.title',
    descriptionKey: 'razorpay.settingsCards.description',
    searchKeywords: ['razorpay', 'upi', 'gateway', 'payment', 'qr', 'india']
  })

  // Full replacement for PaymentCreateModal — same "New payment"/
  // "Cobrar" button, same trigger, same open/created contract; only
  // the modal content behind it changes for India clinics. See
  // components/RazorpayPaymentModal.vue's own docstring. Resolved via
  // `resolveSlot('payments.create.modal', ...)` at each call site
  // (payments/index.vue, PatientPaymentsPanel.vue) — never rendered
  // through the generic <ModuleSlot> (which only forwards `ctx`, not
  // v-model/props/events this component needs).
  registerSlot('payments.create.modal', {
    id: 'razorpay.payments.create.modal',
    component: defineAsyncComponent(() => import('../components/RazorpayPaymentModal.vue')),
    order: 10,
    condition: isIndiaClinicCtx
  })

  // Small "Razorpay · UPI" badge on each gateway-collected payment row
  // — renders nothing for a manually-recorded payment.
  registerSlot('payments.list.row.meta', {
    id: 'razorpay.payments.list.row.meta',
    component: defineAsyncComponent(() => import('../components/RazorpayPaymentBadge.vue')),
    order: 10,
    condition: isIndiaClinicCtx
  })
})
