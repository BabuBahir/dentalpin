<script setup lang="ts">
import { errorDetail } from '~~/app/utils/error'
import { useRazorpay } from '../composables/useRazorpay'

/**
 * Per-clinic Razorpay credentials (Settings → Integrations).
 *
 * Each clinic uses its own Razorpay account. On save the key secret is
 * Fernet-encrypted at rest and never returned by the API — the UI only
 * tells you whether one is stored. Leave the secret field blank to keep
 * the existing secret (an empty/bogus overwrite is refused server-side
 * because the schema enforces min_length=1; keep it simple).
 */
const { t } = useI18n()
const toast = useToast()
const { fetchSettings, saveSettings } = useRazorpay()

const loading = ref(false)
const saving = ref(false)
const configured = ref(false)
const keyId = ref('')
const keySecret = ref('')
const isActive = ref(true)
const hasSecret = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const settings = await fetchSettings()
    configured.value = !!settings.key_id
    keyId.value = settings.key_id ?? ''
    isActive.value = settings.is_active
    hasSecret.value = settings.has_key_secret
  } catch (e) {
    toast.add({ title: t('razorpay.settings.loadError'), description: errorDetail(e), color: 'error' })
  } finally {
    loading.value = false
  }
})

async function onSave() {
  saving.value = true
  try {
    const saved = await saveSettings({
      key_id: keyId.value,
      key_secret: keySecret.value,
      is_active: isActive.value
    })
    configured.value = true
    hasSecret.value = saved.has_key_secret
    keySecret.value = ''
    toast.add({ title: t('razorpay.settings.saved'), color: 'success' })
  } catch (e) {
    toast.add({ title: t('razorpay.settings.saveError'), description: errorDetail(e), color: 'error' })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="space-y-6 max-w-2xl">
    <div>
      <h2 class="text-lg font-semibold">
        {{ t('razorpay.settings.title') }}
      </h2>
      <p class="text-sm text-gray-500">
        {{ t('razorpay.settings.description') }}
      </p>
    </div>

    <USkeleton
      v-if="loading"
      class="h-40 w-full"
    />

    <UCard v-else>
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">{{ t('razorpay.settings.credentials') }}</span>
          <UBadge
            v-if="configured && isActive"
            color="success"
            variant="subtle"
          >
            {{ t('razorpay.settings.active') }}
          </UBadge>
          <UBadge
            v-else
            color="error"
            variant="subtle"
          >
            {{ t('razorpay.settings.inactive') }}
          </UBadge>
        </div>
      </template>

      <div class="space-y-3">
        <UFormField
          :label="t('razorpay.settings.keyId')"
          :help="t('razorpay.settings.keyIdHelp')"
        >
          <UInput
            v-model="keyId"
            placeholder="rzp_live_…"
          />
        </UFormField>

        <UFormField
          :label="t('razorpay.settings.keySecret')"
          :help="hasSecret ? t('razorpay.settings.keySecretStored') : t('razorpay.settings.keySecretHelp')"
        >
          <UInput
            v-model="keySecret"
            type="password"
            placeholder="••••••••"
          />
        </UFormField>

        <UFormField :label="t('razorpay.settings.activeLabel')">
          <USwitch v-model="isActive" />
        </UFormField>

        <div class="flex gap-2">
          <UButton
            icon="i-lucide-save"
            :loading="saving"
            @click="onSave"
          >
            {{ t('common.save') }}
          </UButton>
        </div>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <span class="font-medium">{{ t('razorpay.settings.howTo') }}</span>
      </template>
      <p class="text-sm text-gray-500">
        {{ t('razorpay.settings.howToHelp') }}
      </p>
    </UCard>
  </div>
</template>
