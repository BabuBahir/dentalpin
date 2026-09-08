<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorDetail } from '~~/app/utils/error'
import { useRazorpayCountry } from '../composables/useRazorpay'
import { useRazorpayCheckout } from '../composables/useRazorpayCheckout'

/**
 * "Pagar con Razorpay" — registers into `payments.collect.actions`
 * (#365). Each host passes `ctx = { patient?, budget?, prefer_invoice_id? }`;
 * we render only when a patient is resolvable and the clinic is in India.
 *
 * Security mirror of the backend contract: this component only creates
 * the order and forwards the checkout callback (ids + signature). Amount,
 * currency and method recorded on the Payment come from Razorpay
 * server-side — the web form's amount is used to create the order, and
 * the recorded amount re-verified against the captured payment.
 */

const props = defineProps<{
  ctx?: {
    patient?: { id?: string, full_name?: string } | null
    patient_id?: string
    patientId?: string
    budget?: { id?: string, ref?: string | null, patient_id?: string, patient?: { id?: string } | null } | null
    prefer_invoice_id?: string | null
  } | null
}>()

const { t } = useI18n()
const { can } = usePermissions()
const country = useRazorpayCountry()
const { checkoutOnce } = useRazorpayCheckout()

const patientId = computed(() => (
  props.ctx?.patient?.id
  ?? props.ctx?.patient_id
  ?? props.ctx?.patientId
  ?? props.ctx?.budget?.patient?.id
  ?? props.ctx?.budget?.patient_id
  ?? null
))
const patientName = computed(
  () => props.ctx?.patient?.full_name ?? null
)
const budgetId = computed(() => props.ctx?.budget?.id ?? null)
const budgetRef = computed(() => props.ctx?.budget?.ref ?? null)

const visible = computed(() => (
  can(PERMISSIONS.razorpay.collect)
  && country.value === 'IN'
  && !!patientId.value
))

const open = ref(false)
const amount = ref<number | null>(null)
const paying = ref(false)
const error = ref<string | null>(null)

function startCollect() {
  error.value = null
  const preset = props.ctx?.budget as { pending_amount?: number } | null
  amount.value = (typeof preset?.pending_amount === 'number' && preset.pending_amount > 0) ? preset.pending_amount : null
  open.value = true
}

async function confirmCollect() {
  if (!patientId.value || !amount.value || amount.value <= 0) {
    error.value = t('razorpay.collect.invalidAmount')
    return
  }
  const patientIdValue = patientId.value
  const amountValue = amount.value
  error.value = null
  paying.value = true
  try {
    const outcome = await checkoutOnce({
      patient_id: patientIdValue,
      amount: amountValue,
      payment_date: new Date().toISOString().slice(0, 10),
      allocations: [{
        target_type: budgetId.value ? 'budget' : 'on_account',
        target_id: budgetId.value ?? undefined,
        amount: amountValue
      }]
    })
    if (outcome.ok) {
      open.value = false
      // The payment is now real on the backend. The hosts that
      // render this slot refresh on their own modal events, so
      // reconcile server state with a reload to the same route.
      await reloadNuxtApp()
    } else if (outcome.reason === 'error' || outcome.reason === 'unconfigured') {
      error.value = outcome.error ?? t('razorpay.collect.error')
    }
    // 'cancelled' → popup dismissed without paying; keep the modal open so
    // the user can retry or adjust the amount.
  } catch (e) {
    error.value = errorDetail(e) ?? t('razorpay.collect.error')
  } finally {
    paying.value = false
  }
}
</script>

<template>
  <UButton
    v-if="visible"
    icon="i-lucide-indian-rupee"
    size="sm"
    variant="soft"
    :loading="paying"
    @click="startCollect"
  >
    {{ t('razorpay.collect.button') }}
  </UButton>

  <UModal v-model:open="open">
    <template #content>
      <UCard class="w-full max-w-lg">
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="text-h1 text-default">
              {{ t('razorpay.collect.title') }}
            </h2>
            <UButton
              variant="ghost"
              color="neutral"
              icon="i-lucide-x"
              :aria-label="t('common.close')"
              @click="open = false"
            />
          </div>
        </template>

        <div class="space-y-4">
          <div class="text-sm text-gray-500">
            <template v-if="patientName">
              {{ patientName }}
            </template>
            <template v-else>
              {{ t('razorpay.collect.patient') }}
            </template>
            <template v-if="budgetRef">
              · {{ t('razorpay.collect.budget') }} {{ budgetRef }}
            </template>
          </div>

          <UFormField :label="t('razorpay.collect.amount')">
            <UInput
              v-model.number="amount"
              type="number"
              min="0"
              step="0.01"
              placeholder="0.00"
            />
          </UFormField>

          <p
            v-if="error"
            class="text-sm text-red-500"
          >
            {{ error }}
          </p>

          <div class="flex justify-end gap-2">
            <UButton
              variant="soft"
              @click="open = false"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              color="primary"
              icon="i-lucide-wallet"
              :loading="paying"
              @click="confirmCollect"
            >
              {{ t('razorpay.collect.pay') }}
            </UButton>
          </div>
        </div>
      </UCard>
    </template>
  </UModal>
</template>
