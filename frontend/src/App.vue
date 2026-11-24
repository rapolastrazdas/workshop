<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { api, ApiError, auth, clearSession } from './auth'
import { router } from './router'
import DeleteAccountDialog from './components/DeleteAccountDialog.vue'

const loggingOut = ref(false)
const logoutError = ref('')
const deletingAccount = ref(false)

async function logout() {
  if (loggingOut.value) return
  loggingOut.value = true
  logoutError.value = ''
  try {
    await api('/auth/logout', { method: 'POST' })
    clearSession()
    auth.notice = ''
    await router.replace({ name: 'home' })
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 401)) {
      logoutError.value = error instanceof Error ? error.message : 'Nepavyko atsijungti. Bandykite dar kartą.'
    }
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <div class="app-shell">
    <header class="site-header">
      <RouterLink class="brand" :to="auth.session ? '/mano-kalades' : '/'">Urza's Workshop</RouterLink>
      <nav aria-label="Paskyra">
        <template v-if="auth.session">
          <span class="account-email">{{ auth.session.user.email }}</span>
          <button class="button" :disabled="loggingOut" @click="logout">{{ loggingOut ? 'Atsijungiama…' : 'Atsijungti' }}</button>
          <button class="button button-danger" :disabled="loggingOut" @click="deletingAccount = true">Šalinti paskyrą</button>
        </template>
        <template v-else>
          <RouterLink class="button" to="/prisijungimas">Prisijungti</RouterLink>
          <RouterLink class="button button-primary" to="/registracija">Registruotis</RouterLink>
        </template>
      </nav>
    </header>
    <DeleteAccountDialog v-if="deletingAccount && auth.session" @close="deletingAccount = false" />
    <div v-if="logoutError" class="global-notice error-banner" role="alert">{{ logoutError }}</div>
    <main id="main-content">
      <div v-if="auth.notice" class="global-notice info-banner" role="alert">{{ auth.notice }}</div>
      <RouterView :key="$route.path" />
    </main>
    <footer class="site-footer">
      <p>Urza’s Workshop yra neoficialus gerbėjų turinys, leidžiamas pagal „Fan Content Policy“. Jo nepatvirtino ir neremia „Wizards“. Dalis naudojamos medžiagos priklauso „Wizards of the Coast“. ©Wizards of the Coast LLC.</p>
      <p>Kortų duomenys ir vaizdai – <a href="https://scryfall.com" target="_blank" rel="noopener noreferrer">Scryfall</a></p>
    </footer>
  </div>
</template>
