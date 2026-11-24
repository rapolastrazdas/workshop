<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api, ApiError, auth, clearSession } from '../auth'
import { router } from '../router'

const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
const passwordInput = ref<HTMLInputElement>()
const password = ref('')
const passwordError = ref('')
const message = ref('')
const busy = ref(false)
let previousFocus: HTMLElement | null = null

onMounted(() => {
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  dialog.value?.showModal()
  passwordInput.value?.focus()
})

onBeforeUnmount(() => {
  password.value = ''
  dialog.value?.close()
  previousFocus?.focus()
})

watch(() => auth.session, (session) => {
  if (!session) emit('close')
})

function cancel(event?: Event) {
  event?.preventDefault()
  if (!busy.value) emit('close')
}

async function removeAccount() {
  if (busy.value) return
  passwordError.value = ''
  message.value = ''
  if (!password.value) {
    passwordError.value = 'Įveskite slaptažodį.'
    passwordInput.value?.focus()
    return
  }
  busy.value = true
  try {
    await api('/auth/account', { method: 'DELETE', body: JSON.stringify({ password: password.value }) })
    password.value = ''
    clearSession()
    auth.notice = 'Paskyra ištrinta.'
    emit('close')
    await router.replace({ name: 'home' })
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      passwordError.value = 'Neteisingas slaptažodis.'
      password.value = ''
      await nextTick()
      passwordInput.value?.focus()
    } else if (!(error instanceof ApiError && error.status === 401)) {
      message.value = error instanceof Error ? error.message : 'Nepavyko pašalinti paskyros. Bandykite dar kartą.'
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <dialog ref="dialog" class="account-dialog" aria-labelledby="delete-title" aria-describedby="delete-description" @cancel="cancel">
    <div class="dialog-header">
      <h2 id="delete-title">Šalinti paskyrą?</h2>
      <button class="dialog-close" type="button" aria-label="Uždaryti" :disabled="busy" @click="cancel()">×</button>
    </div>
    <p id="delete-description">Jūsų paskyra ir visos jūsų kaladės bus ištrintos. Šio veiksmo atšaukti negalima. Norėdami patvirtinti, įveskite slaptažodį.</p>
    <form novalidate :aria-busy="busy" @submit.prevent="removeAccount">
      <div class="field">
        <label for="delete-password">Slaptažodis</label>
        <input id="delete-password" ref="passwordInput" v-model="password" type="password" autocomplete="current-password"
          required :disabled="busy" :aria-invalid="Boolean(passwordError)" :aria-describedby="passwordError ? 'delete-password-error' : undefined" />
        <p v-if="passwordError" id="delete-password-error" class="field-error" role="alert">{{ passwordError }}</p>
      </div>
      <div v-if="message" class="error-banner" role="alert">{{ message }}</div>
      <div class="dialog-actions">
        <button class="button" type="button" :disabled="busy" @click="cancel()">Atšaukti</button>
        <button class="button button-destructive" type="submit" :disabled="busy">{{ busy ? 'Šalinama…' : 'Šalinti paskyrą' }}</button>
      </div>
    </form>
  </dialog>
</template>
