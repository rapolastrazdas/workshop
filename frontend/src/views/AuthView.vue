<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ApiError, authenticate } from '../auth'
import { router } from '../router'

const props = defineProps<{ mode: 'register' | 'login' }>()
const registering = computed(() => props.mode === 'register')
const title = computed(() => registering.value ? 'Registracija' : 'Prisijungimas')
const form = reactive({ email: '', password: '', password_confirmation: '' })
const errors = reactive<Record<string, string>>({})
const message = ref('')
const busy = ref(false)

function validate() {
  for (const key of Object.keys(errors)) delete errors[key]
  if (!form.email.trim()) errors.email = 'Įveskite el. pašto adresą.'
  else if (registering.value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
    errors.email = 'Įveskite teisingą el. pašto adresą.'
  }
  if (registering.value) {
    if (Array.from(form.password).length <= 8) errors.password = 'Slaptažodį turi sudaryti daugiau nei 8 simboliai.'
    else if (Array.from(form.password).length > 1024) errors.password = 'Slaptažodis negali būti ilgesnis nei 1024 simboliai.'
    if (form.password !== form.password_confirmation) errors.password_confirmation = 'Slaptažodžiai nesutampa.'
  } else if (!form.password) errors.password = 'Įveskite slaptažodį.'
  return Object.keys(errors).length === 0
}

async function submit() {
  if (busy.value) return
  message.value = ''
  if (!validate()) {
    focusInvalid()
    return
  }
  busy.value = true
  try {
    await authenticate(props.mode, { ...form })
    form.password = ''
    form.password_confirmation = ''
    await router.replace({ name: 'decks' })
  } catch (error) {
    if (error instanceof ApiError && typeof error.detail === 'object' && error.detail !== null && 'errors' in error.detail) {
      Object.assign(errors, error.detail.errors)
      focusInvalid()
    } else message.value = error instanceof Error ? error.message : 'Nepavyko atlikti veiksmo. Bandykite dar kartą.'
  } finally {
    busy.value = false
  }
}

function focusInvalid() {
  document.getElementById(Object.keys(errors)[0] || '')?.focus()
}
</script>

<template>
  <section class="auth-area" :aria-labelledby="'auth-title'">
    <div class="auth-card">
      <h1 id="auth-title">{{ title }}</h1>
      <form novalidate :aria-busy="busy" @submit.prevent="submit">
        <div class="field">
          <label for="email">El. paštas</label>
          <input id="email" v-model="form.email" name="email" type="email" autocomplete="username" inputmode="email"
            placeholder="vardas@pastas.lt" required :aria-invalid="Boolean(errors.email)"
            :aria-describedby="errors.email ? 'email-error' : undefined" />
          <p v-if="errors.email" id="email-error" class="field-error" role="alert">{{ errors.email }}</p>
        </div>
        <div class="field">
          <label for="password">Slaptažodis</label>
          <input id="password" v-model="form.password" name="password" type="password"
            :autocomplete="registering ? 'new-password' : 'current-password'" required
            :aria-invalid="Boolean(errors.password)" :aria-describedby="errors.password ? 'password-error' : undefined" />
          <p v-if="errors.password" id="password-error" class="field-error" role="alert">{{ errors.password }}</p>
        </div>
        <div v-if="registering" class="field">
          <label for="password_confirmation">Pakartokite slaptažodį</label>
          <input id="password_confirmation" v-model="form.password_confirmation" name="password_confirmation"
            type="password" autocomplete="new-password" required :aria-invalid="Boolean(errors.password_confirmation)"
            :aria-describedby="errors.password_confirmation ? 'confirmation-error' : undefined" />
          <p v-if="errors.password_confirmation" id="confirmation-error" class="field-error" role="alert">{{ errors.password_confirmation }}</p>
        </div>
        <div v-if="message" class="error-banner" role="alert"><span class="error-icon" aria-hidden="true">!</span>{{ message }}</div>
        <button class="button button-primary submit-button" type="submit" :disabled="busy">
          {{ busy ? (registering ? 'Registruojama…' : 'Jungiamasi…') : (registering ? 'Registruotis' : 'Prisijungti') }}
        </button>
      </form>
      <p class="auth-switch" v-if="registering">Jau turite paskyrą? <RouterLink to="/prisijungimas">Prisijungti</RouterLink></p>
      <p class="auth-switch" v-else>Neturite paskyros? <RouterLink to="/registracija">Registruotis</RouterLink></p>
    </div>
  </section>
</template>
