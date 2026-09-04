<script setup lang="ts">
/**
 * India-aware "Record payment" — replaces PaymentCreateModal.vue at
 * the call site (via the `payments.create.modal` slot override, India
 * clinics only; see plugins/slots.client.ts), not inside it. The
 * "New payment"/"Cobrar" button keeps its label and location; only
 * what opens changes. Non-India clinics never load this component.
 *
 * Everything from the base modal (patient search, amount, method
 * chips Cash/Card/Transfer/Insurance + "More options", date, advanced
 * reference/notes, cancel) behaves identically — the manual submit
 * path calls the exact same `usePayments().create()` the base modal
 * uses. What's added, India-only:
 *  - three extra method rails: UPI (manual — instant record, no
 *    gateway involved), UPI QR and Razorpay (both gateway rails via
 *    payment_gateways/razorpay). PhonePe is deliberately not rendered
 *    yet — no adapter exists for it in this PR.
 *  - "Apply to" becomes a table: every open budget as its own
 *    editable-amount row, plus an always-present "On account" row,
 *    instead of a single dropdown target.
 *  - a running received/allocated/unallocated footer.
 *  - gateway rails hand off to a waiting state (checkout/QR/link) and
 *    only emit `created` once payment_gateways reports the request
 *    `succeeded` — never on a browser redirect/callback alone.
 */

import type {
  BudgetListItem,
  Patient,
  PaymentAllocationCreate,
  PaymentMethod,
  PaymentRecord
} from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'
import type { GatewayMethod, PaymentRequest } from '../composables/useRazorpay'

const props = withDefaults(defineProps<{
  open: boolean
  defaultPatientId?: string
  defaultPatientName?: string
  defaultBudgetId?: string
  defaultAmount?: number
  budgetLabel?: string
  suggestedAmount?: number
}>(), {
  defaultPatientId: '',
  defaultPatientName: '',
  defaultBudgetId: undefined,
  defaultAmount: 0,
  budgetLabel: undefined,
  suggestedAmount: undefined
})

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'created', payment: PaymentRecord): void
}>()

const { t } = useI18n()
const toast = useToast()
const { create: createManualPayment } = usePayments()
const {
  getSettings,
  createPaymentRequest,
  getPaymentRequest,
  refreshPaymentRequest,
  cancelPaymentRequest
} = useRazorpay()
const api = useApi()
const { format: formatCurrency, symbol: currencySymbol } = useCurrency()

const isBudgetContext = computed(() => Boolean(props.defaultBudgetId))
const isPatientLocked = computed(() => Boolean(props.defaultPatientId))

// --- Rails ---------------------------------------------------------------

interface Rail {
  id: string
  icon: string
  kind: 'manual' | 'gateway'
  method?: PaymentMethod // kind === 'manual'
  gatewayMethod?: GatewayMethod // kind === 'gateway'
}

const PRIMARY_RAILS: Rail[] = [
  { id: 'cash', kind: 'manual', method: 'cash', icon: 'i-lucide-banknote' },
  { id: 'card', kind: 'manual', method: 'card', icon: 'i-lucide-credit-card' },
  { id: 'bank_transfer', kind: 'manual', method: 'bank_transfer', icon: 'i-lucide-building-2' },
  { id: 'insurance', kind: 'manual', method: 'insurance', icon: 'i-lucide-shield' }
]
// India-only, appended after the four above — order matters, existing
// four keep their positions.
const INDIA_RAILS: Rail[] = [
  { id: 'upi_manual', kind: 'manual', method: 'upi', icon: 'i-lucide-smartphone' },
  { id: 'upi_qr', kind: 'gateway', gatewayMethod: 'qr', icon: 'i-lucide-qr-code' },
  { id: 'razorpay', kind: 'gateway', gatewayMethod: 'card', icon: 'i-lucide-zap' }
]
const SECONDARY_RAILS: Rail[] = [
  { id: 'direct_debit', kind: 'manual', method: 'direct_debit', icon: 'i-lucide-repeat' },
  { id: 'other', kind: 'manual', method: 'other', icon: 'i-lucide-more-horizontal' }
]

function railLabel(rail: Rail): string {
  if (rail.id === 'upi_manual') return t('razorpay.paymentModal.railUpiManual')
  if (rail.id === 'upi_qr') return t('razorpay.paymentModal.railUpiQr')
  if (rail.id === 'razorpay') return t('razorpay.paymentModal.railRazorpay')
  return t(`payments.methods.${rail.method}`)
}

const isGatewayConfigured = ref(false)
const isCheckingConfig = ref(true)

onMounted(async () => {
  try {
    const settings = await getSettings()
    isGatewayConfigured.value = settings.is_active && settings.has_key_secret
  } catch {
    isGatewayConfigured.value = false
  } finally {
    isCheckingConfig.value = false
  }
})

const selectedRailId = ref<string>('cash')
const selectedRail = computed<Rail | undefined>(() =>
  [...PRIMARY_RAILS, ...INDIA_RAILS, ...SECONDARY_RAILS].find(r => r.id === selectedRailId.value)
)
const isGatewayRail = computed(() => selectedRail.value?.kind === 'gateway')
const showSecondaryMethods = ref(false)

function pickRail(id: string) {
  selectedRailId.value = id
}

// --- Patient / amount ------------------------------------------------------

const selectedPatient = ref<Patient | null>(null)
const patientId = computed(() => props.defaultPatientId || selectedPatient.value?.id || '')

const amount = ref(props.defaultAmount ?? 0)
const paymentDate = ref(new Date().toISOString().slice(0, 10))
const reference = ref('')
const notes = ref('')
const showAdvanced = ref(false)
const isToday = computed(() => paymentDate.value === new Date().toISOString().slice(0, 10))

const suggestedDiffers = computed(() => {
  if (props.suggestedAmount === undefined) return false
  return Math.abs(Number(amount.value) - props.suggestedAmount) > 0.001
})
function applySuggestion() {
  if (props.suggestedAmount !== undefined) amount.value = props.suggestedAmount
}

// --- Allocation table ------------------------------------------------------

interface AllocationRow {
  targetType: 'budget' | 'on_account'
  budgetId?: string
  label: string
  pending?: number
  amountValue: number
  locked: boolean
}

const budgetRows = ref<AllocationRow[]>([])
const onAccountRow = ref<AllocationRow>({
  targetType: 'on_account',
  label: '',
  amountValue: 0,
  locked: false
})

async function loadBudgetRows() {
  if (!patientId.value) {
    budgetRows.value = []
    return
  }
  try {
    const params = new URLSearchParams({ patient_id: patientId.value, page_size: '100' })
    params.append('status', 'accepted')
    params.append('status', 'completed')
    const res = await api.get<{ data: BudgetListItem[] }>(`/api/v1/budget/budgets?${params}`)
    const list = res.data
    const summaries: Record<string, { pending: string }> = list.length
      ? await api.post<{ data: { summaries: Record<string, { pending: string }> } }>(
          '/api/v1/payments/summary/by-budgets',
          { budget_ids: list.map(b => b.id) }
        ).then(r => r.data.summaries).catch(() => ({}))
      : {}
    budgetRows.value = list.map((b) => {
      const summary = summaries[b.id]
      return {
        targetType: 'budget' as const,
        budgetId: b.id,
        label: b.budget_number,
        pending: summary ? Number(summary.pending) : undefined,
        amountValue: b.id === props.defaultBudgetId ? Number(props.defaultAmount ?? 0) : 0,
        locked: b.id === props.defaultBudgetId && isBudgetContext.value
      }
    })
  } catch {
    budgetRows.value = []
  }
}

watch(patientId, loadBudgetRows, { immediate: true })

// Default distribution: locked budget context absorbs the full
// amount; otherwise on_account does, matching the base modal's
// existing default (issue #178 — never leave the split ambiguous).
function resetAllocations() {
  onAccountRow.value = {
    targetType: 'on_account',
    label: t('payments.target.onAccount'),
    amountValue: isBudgetContext.value ? 0 : Number(amount.value) || 0,
    locked: false
  }
  for (const row of budgetRows.value) {
    if (!row.locked) row.amountValue = 0
  }
}

const allocationRows = computed<AllocationRow[]>(() => [...budgetRows.value, onAccountRow.value])
const allocatedTotal = computed(() =>
  allocationRows.value.reduce((sum, r) => sum + (Number(r.amountValue) || 0), 0)
)
const unallocated = computed(() => Number(amount.value || 0) - allocatedTotal.value)
const isBalanced = computed(() => Math.abs(unallocated.value) <= 0.001)

function buildAllocations(): PaymentAllocationCreate[] {
  return allocationRows.value
    .filter(r => Number(r.amountValue) > 0)
    .map(r => ({
      target_type: r.targetType,
      target_id: r.targetType === 'budget' ? r.budgetId : undefined,
      amount: Number(r.amountValue)
    }))
}

// --- Reset on open -----------------------------------------------------

const formError = ref<string | null>(null)
const amountInputRef = ref<HTMLInputElement | null>(null)

watch(() => props.open, async (isOpen) => {
  if (!isOpen) return
  selectedPatient.value = null
  amount.value = props.defaultAmount ?? 0
  paymentDate.value = new Date().toISOString().slice(0, 10)
  reference.value = ''
  notes.value = ''
  showAdvanced.value = false
  showSecondaryMethods.value = false
  selectedRailId.value = 'cash'
  formError.value = null
  gatewayRequest.value = null
  stopPolling()
  await loadBudgetRows()
  resetAllocations()
  await nextTick()
  amountInputRef.value?.focus()
  amountInputRef.value?.select()
})

watch(amount, () => {
  if (!gatewayRequest.value) resetAllocations()
})

const canSubmit = computed(() =>
  Boolean(patientId.value) && Number(amount.value) > 0 && isBalanced.value && allocatedTotal.value > 0
)

// --- Manual submit (identical to the base modal's own path) ------------

const isSubmitting = ref(false)

async function submitManual() {
  if (!selectedRail.value?.method) return
  isSubmitting.value = true
  try {
    const created = await createManualPayment({
      patient_id: patientId.value,
      amount: Number(amount.value),
      method: selectedRail.value.method,
      payment_date: paymentDate.value,
      reference: reference.value || undefined,
      notes: notes.value || undefined,
      allocations: buildAllocations()
    })
    if (created) {
      emit('created', created)
      emit('update:open', false)
    } else {
      formError.value = t('payments.new.errUnknown')
    }
  } finally {
    isSubmitting.value = false
  }
}

// --- Gateway submit (hand-off, never authoritative on its own) ---------

const gatewayRequest = ref<PaymentRequest | null>(null)
const isRefreshingGateway = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null
const TERMINAL_STATES = ['succeeded', 'failed', 'expired', 'cancelled']

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling(id: string) {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const fresh = await getPaymentRequest(id)
      gatewayRequest.value = fresh
      if (TERMINAL_STATES.includes(fresh.state)) {
        stopPolling()
        if (fresh.state === 'succeeded' && fresh.payment_id) {
          await onGatewaySucceeded(fresh.payment_id)
        }
      }
    } catch {
      // transient poll failure — next tick retries
    }
  }, 3000)
}

async function onGatewaySucceeded(paymentId: string) {
  const { get } = usePayments()
  const payment = await get(paymentId)
  if (payment) {
    toast.add({ title: t('common.success'), description: t('razorpay.collect.success'), color: 'success' })
    emit('created', payment)
  }
}

let checkoutJsPromise: Promise<void> | null = null
function loadCheckoutJs(): Promise<void> {
  if (checkoutJsPromise) return checkoutJsPromise
  checkoutJsPromise = new Promise((resolve, reject) => {
    if ((window as unknown as { Razorpay?: unknown }).Razorpay) {
      resolve()
      return
    }
    const script = document.createElement('script')
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('checkout.js failed to load'))
    document.head.appendChild(script)
  })
  return checkoutJsPromise
}

async function openCheckoutJs(req: PaymentRequest) {
  if (!req.checkout?.checkout_payload) return
  try {
    await loadCheckoutJs()
  } catch {
    toast.add({ title: t('common.error'), description: t('razorpay.collect.checkoutLoadError'), color: 'error' })
    return
  }
  interface RazorpayCheckout { open: () => void }
  interface RazorpayCtor { new (options: Record<string, unknown>): RazorpayCheckout }
  const RazorpayCtor = (window as unknown as { Razorpay: RazorpayCtor }).Razorpay
  const instance = new RazorpayCtor({
    ...req.checkout.checkout_payload,
    handler: () => startPolling(req.id) // browser callback — cue to poll, never authoritative
  })
  instance.open()
}

async function submitGateway() {
  if (!selectedRail.value?.gatewayMethod) return
  isSubmitting.value = true
  formError.value = null
  try {
    const created = await createPaymentRequest({
      patient_id: patientId.value,
      amount: Number(amount.value),
      method: selectedRail.value.gatewayMethod,
      allocations: buildAllocations()
    })
    gatewayRequest.value = created
    if (selectedRail.value.gatewayMethod === 'card') {
      await openCheckoutJs(created)
    }
    startPolling(created.id)
  } catch (e) {
    formError.value = errorMessage(e, t('razorpay.collect.createError'))
  } finally {
    isSubmitting.value = false
  }
}

async function submit() {
  formError.value = null
  if (!patientId.value) {
    formError.value = t('payments.new.errPatient')
    return
  }
  if (!(Number(amount.value) > 0)) {
    formError.value = t('payments.new.errAmount')
    return
  }
  if (!isBalanced.value) {
    formError.value = t('payments.new.errSum')
    return
  }
  if (isGatewayRail.value) await submitGateway()
  else await submitManual()
}

async function copyLink() {
  const url = gatewayRequest.value?.checkout?.redirect_url
  if (!url) return
  try {
    await navigator.clipboard.writeText(url)
    toast.add({ title: t('razorpay.collect.linkCopied'), color: 'success' })
  } catch {
    // clipboard unavailable — field stays visible to copy by hand
  }
}

async function manualRefreshGateway() {
  if (!gatewayRequest.value) return
  isRefreshingGateway.value = true
  try {
    const fresh = await refreshPaymentRequest(gatewayRequest.value.id)
    gatewayRequest.value = fresh
    if (fresh.state === 'succeeded' && fresh.payment_id) await onGatewaySucceeded(fresh.payment_id)
  } finally {
    isRefreshingGateway.value = false
  }
}

async function cancelGatewayRequest() {
  if (!gatewayRequest.value) return
  try {
    gatewayRequest.value = await cancelPaymentRequest(gatewayRequest.value.id)
  } finally {
    stopPolling()
  }
}

function tryGatewayAgain() {
  gatewayRequest.value = null
  stopPolling()
}

onBeforeUnmount(() => stopPolling())

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && canSubmit.value && !gatewayRequest.value) {
    e.preventDefault()
    submit()
  }
}

function close() {
  emit('update:open', false)
}
</script>

<template>
  <UModal
    :open="open"
    :title="t('payments.new.title')"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <div
        class="space-y-5"
        @keydown="handleKeydown"
      >
        <template v-if="!gatewayRequest">
          <div
            v-if="isPatientLocked"
            class="flex items-center gap-3 p-3 rounded-token-md bg-surface-muted"
          >
            <UAvatar
              :alt="defaultPatientName || ''"
              size="md"
              icon="i-lucide-user"
            />
            <div class="min-w-0">
              <div class="text-xs text-muted uppercase tracking-wide">
                {{ t('payments.new.patient') }}
              </div>
              <div class="font-medium truncate">
                {{ defaultPatientName || t('payments.new.unknownPatient') }}
              </div>
            </div>
          </div>
          <UFormField
            v-else
            :label="t('payments.new.patient')"
          >
            <PatientVisualSelector
              v-model="selectedPatient"
              in-modal
              :placeholder="t('payments.new.patientPlaceholder')"
            />
          </UFormField>

          <div>
            <label class="block text-xs text-muted uppercase tracking-wide mb-1">
              {{ t('payments.new.amount') }}
            </label>
            <div class="relative">
              <input
                ref="amountInputRef"
                v-model.number="amount"
                type="number"
                step="0.01"
                min="0"
                inputmode="decimal"
                class="w-full text-3xl font-semibold py-3 px-4 pr-14 rounded-token-md border border-default bg-surface focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] tnum"
              >
              <span class="absolute right-4 top-1/2 -translate-y-1/2 text-xl text-muted pointer-events-none">{{ currencySymbol() }}</span>
            </div>
            <div
              v-if="suggestedAmount !== undefined && suggestedAmount > 0"
              class="mt-1 text-xs text-muted flex items-center gap-2"
            >
              <span>{{ t('payments.new.suggestedHint', { amount: formatCurrency(suggestedAmount) }) }}</span>
              <button
                v-if="suggestedDiffers"
                type="button"
                class="text-primary-accent hover:underline"
                @click="applySuggestion"
              >
                {{ t('payments.new.useSuggested') }}
              </button>
            </div>
          </div>

          <!-- Apply to — allocation table (India: always the table, no
                 single-dropdown/advanced split). -->
          <div>
            <label class="block text-xs text-muted uppercase tracking-wide mb-1">
              {{ t('payments.target.label') }}
            </label>
            <div class="space-y-1.5">
              <div
                v-for="row in budgetRows"
                :key="row.budgetId"
                class="flex items-center gap-2"
              >
                <div class="flex-1 min-w-0 text-sm">
                  <div class="truncate">
                    {{ row.label }}
                  </div>
                  <div
                    v-if="row.pending !== undefined"
                    class="text-caption text-subtle"
                  >
                    {{ t('razorpay.paymentModal.pending', { amount: formatCurrency(row.pending) }) }}
                  </div>
                </div>
                <UInput
                  v-model.number="row.amountValue"
                  type="number"
                  step="0.01"
                  min="0"
                  class="w-32"
                  :disabled="row.locked"
                />
              </div>
              <div class="flex items-center gap-2">
                <div class="flex-1 min-w-0 text-sm">
                  {{ t('payments.target.onAccount') }}
                </div>
                <UInput
                  v-model.number="onAccountRow.amountValue"
                  type="number"
                  step="0.01"
                  min="0"
                  class="w-32"
                />
              </div>
            </div>
            <p
              v-if="budgetRows.length === 0"
              class="mt-1 text-xs text-muted"
            >
              {{ t('payments.target.onAccountHint') }}
            </p>
          </div>

          <!-- Method — chips. Existing four keep their positions; three
                 India-only rails appended before "More options". -->
          <div>
            <label class="block text-xs text-muted uppercase tracking-wide mb-2">
              {{ t('payments.new.method') }}
            </label>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="m in PRIMARY_RAILS"
                :key="m.id"
                type="button"
                class="method-chip"
                :class="{ active: selectedRailId === m.id }"
                @click="pickRail(m.id)"
              >
                <UIcon
                  :name="m.icon"
                  class="w-4 h-4"
                />
                <span>{{ railLabel(m) }}</span>
              </button>
              <button
                v-for="m in INDIA_RAILS"
                :key="m.id"
                type="button"
                class="method-chip"
                :class="{ active: selectedRailId === m.id }"
                :disabled="m.kind === 'gateway' && !isCheckingConfig && !isGatewayConfigured"
                :title="m.kind === 'gateway' && !isGatewayConfigured ? t('razorpay.collect.notConfiguredHint') : undefined"
                @click="pickRail(m.id)"
              >
                <UIcon
                  :name="m.icon"
                  class="w-4 h-4"
                />
                <span>{{ railLabel(m) }}</span>
              </button>
              <button
                v-if="!showSecondaryMethods && !SECONDARY_RAILS.some(m => m.id === selectedRailId)"
                type="button"
                class="method-chip ghost"
                @click="showSecondaryMethods = true"
              >
                <UIcon
                  name="i-lucide-plus"
                  class="w-4 h-4"
                />
                <span>{{ t('payments.new.moreMethods') }}</span>
              </button>
              <button
                v-for="m in SECONDARY_RAILS"
                v-show="showSecondaryMethods || selectedRailId === m.id"
                :key="m.id"
                type="button"
                class="method-chip"
                :class="{ active: selectedRailId === m.id }"
                @click="pickRail(m.id)"
              >
                <UIcon
                  :name="m.icon"
                  class="w-4 h-4"
                />
                <span>{{ railLabel(m) }}</span>
              </button>
            </div>
          </div>

          <!-- Fecha -->
          <div>
            <label class="block text-xs text-muted uppercase tracking-wide mb-1">
              {{ t('payments.new.date') }}
            </label>
            <div class="flex items-center gap-2">
              <input
                v-model="paymentDate"
                type="date"
                class="text-sm py-1.5 px-2 rounded-token-md border border-default bg-surface focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              >
              <UBadge
                v-if="isToday"
                color="success"
                variant="subtle"
                size="xs"
              >
                {{ t('payments.new.today') }}
              </UBadge>
            </div>
          </div>

          <div class="border-t border-default pt-3">
            <button
              type="button"
              class="flex items-center gap-1 text-sm text-muted hover:text-default"
              @click="showAdvanced = !showAdvanced"
            >
              <UIcon
                :name="showAdvanced ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                class="w-4 h-4"
              />
              <span>{{ t('payments.new.advanced') }}</span>
            </button>
            <div
              v-if="showAdvanced"
              class="mt-3 space-y-4"
            >
              <UFormField :label="t('payments.new.reference')">
                <UInput
                  v-model="reference"
                  :placeholder="t('payments.new.referencePlaceholder')"
                />
              </UFormField>
              <UFormField :label="t('payments.new.notes')">
                <UInput v-model="notes" />
              </UFormField>
            </div>
          </div>

          <!-- Footer summary: received / allocated / unallocated -->
          <div class="flex items-center justify-between text-caption rounded-token-md bg-surface-muted p-3">
            <span class="text-subtle">{{ t('razorpay.paymentModal.received') }} {{ formatCurrency(amount) }}</span>
            <span class="text-subtle">{{ t('razorpay.paymentModal.allocated') }} {{ formatCurrency(allocatedTotal) }}</span>
            <span :class="isBalanced ? 'text-subtle' : 'text-danger-accent font-medium'">
              {{ t('razorpay.paymentModal.unallocated') }} {{ formatCurrency(unallocated) }}
            </span>
          </div>

          <p
            v-if="formError"
            class="text-sm text-danger-accent"
          >
            {{ formError }}
          </p>
        </template>

        <!-- Gateway hand-off states -->
        <template v-else>
          <div
            v-if="gatewayRequest.state === 'awaiting_customer_action'"
            class="space-y-3"
          >
            <div
              v-if="selectedRail?.gatewayMethod === 'qr' && gatewayRequest.checkout?.qr_image_url"
              class="text-center"
            >
              <img
                :src="gatewayRequest.checkout.qr_image_url"
                :alt="t('razorpay.collect.scanQr')"
                class="mx-auto w-48 h-48 rounded-token-md border border-default"
              >
              <p class="text-caption text-subtle mt-2">
                {{ t('razorpay.collect.scanQr') }}
              </p>
            </div>
            <div
              v-else-if="gatewayRequest.checkout?.redirect_url"
              class="space-y-2"
            >
              <UInput
                :model-value="gatewayRequest.checkout.redirect_url"
                readonly
                class="font-mono text-xs"
              />
              <UButton
                variant="soft"
                icon="i-lucide-copy"
                @click="copyLink"
              >
                {{ t('common.copy') }}
              </UButton>
            </div>
            <div
              v-else
              class="text-center"
            >
              <UButton
                color="primary"
                icon="i-lucide-credit-card"
                @click="openCheckoutJs(gatewayRequest)"
              >
                {{ t('razorpay.collect.openCheckout') }}
              </UButton>
            </div>
            <div class="flex items-center justify-center gap-2 text-caption text-subtle">
              <UIcon
                name="i-lucide-loader-2"
                class="animate-spin w-4 h-4"
              />
              {{ t('razorpay.collect.waiting') }}
            </div>
            <div class="flex justify-center gap-2">
              <UButton
                size="xs"
                variant="ghost"
                :loading="isRefreshingGateway"
                @click="manualRefreshGateway"
              >
                {{ t('razorpay.collect.checkStatus') }}
              </UButton>
              <UButton
                size="xs"
                variant="ghost"
                color="neutral"
                @click="cancelGatewayRequest"
              >
                {{ t('common.cancel') }}
              </UButton>
            </div>
          </div>

          <div
            v-else-if="gatewayRequest.state === 'authorised_awaiting_capture'"
            class="text-center space-y-2 py-4"
          >
            <UIcon
              name="i-lucide-loader-2"
              class="animate-spin w-8 h-8 mx-auto text-primary"
            />
            <p>{{ t('razorpay.collect.authorizing') }}</p>
          </div>

          <div
            v-else-if="gatewayRequest.state === 'succeeded'"
            class="text-center space-y-3 py-4"
          >
            <UIcon
              name="i-lucide-circle-check"
              class="w-10 h-10 mx-auto text-success"
            />
            <p class="font-medium">
              {{ t('razorpay.collect.success') }}
            </p>
            <UButton
              block
              color="primary"
              @click="close"
            >
              {{ t('common.close') }}
            </UButton>
          </div>

          <div
            v-else
            class="text-center space-y-3 py-4"
          >
            <UIcon
              name="i-lucide-circle-x"
              class="w-10 h-10 mx-auto text-danger"
            />
            <p class="font-medium">
              {{ t(`razorpay.collect.states.${gatewayRequest.state}`) }}
            </p>
            <p
              v-if="gatewayRequest.error_message"
              class="text-caption text-subtle"
            >
              {{ gatewayRequest.error_message }}
            </p>
            <UButton
              block
              color="primary"
              @click="tryGatewayAgain"
            >
              {{ t('razorpay.collect.tryAgain') }}
            </UButton>
          </div>
        </template>
      </div>
    </template>

    <template
      v-if="!gatewayRequest"
      #footer
    >
      <div class="flex justify-end gap-2">
        <UButton
          variant="ghost"
          @click="close"
        >
          {{ t('payments.new.cancel') }}
        </UButton>
        <UButton
          color="primary"
          :icon="isGatewayRail ? 'i-lucide-arrow-right' : 'i-lucide-check'"
          :loading="isSubmitting"
          :disabled="!canSubmit"
          @click="submit"
        >
          {{
            isGatewayRail
              ? t('razorpay.paymentModal.continueWith', { provider: railLabel(selectedRail!) })
              : t('payments.new.submitWithAmount', { amount: formatCurrency(amount) })
          }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.method-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: var(--radius-md, 8px);
  border: 1px solid var(--color-border-default, #E5E7EB);
  background: var(--color-surface, #FFFFFF);
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-default, #1F2937);
  cursor: pointer;
  transition: all 120ms ease;
}

.method-chip:hover:not(:disabled) {
  background: var(--color-surface-muted, #F3F4F6);
}

.method-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.method-chip.active {
  background: var(--color-primary, #3B82F6);
  border-color: var(--color-primary, #3B82F6);
  color: white;
}

.method-chip.ghost {
  border-style: dashed;
  color: var(--color-text-muted, #6B7280);
}

.tnum {
  font-variant-numeric: tabular-nums;
}
</style>
