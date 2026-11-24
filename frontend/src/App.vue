<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { api, ApiError, auth, clearSession } from './auth'
import { router } from './router'
import DeleteAccountDialog from './components/DeleteAccountDialog.vue'
import { dismissNotice, notice, showNotice } from './notices'

const loggingOut = ref(false)
const deletingAccount = ref(false)

async function logout() {
  if (loggingOut.value) return
  loggingOut.value = true
  dismissNotice()
  try {
    await api('/auth/logout', { method: 'POST' })
    clearSession()
    await router.replace({ name: 'home' })
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 401)) {
      showNotice(error instanceof Error ? error.message : 'Nepavyko atsijungti. Bandykite dar kartą.',
        router.currentRoute.value.path, 'error')
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
    <main id="main-content">
      <div v-if="notice.message" class="global-notice notice-banner" :class="notice.kind === 'error' ? 'error-banner' : 'info-banner'" role="alert">
        <span>{{ notice.message }}</span>
        <button class="dialog-close" type="button" aria-label="Uždaryti pranešimą" @click="dismissNotice">×</button>
      </div>
      <RouterView :key="$route.path" />
    </main>
    <footer class="site-footer">
      <p>Urza’s Workshop yra neoficialus gerbėjų turinys, leidžiamas pagal „Fan Content Policy“. Jo nepatvirtino ir neremia „Wizards“. Dalis naudojamos medžiagos priklauso „Wizards of the Coast“. ©Wizards of the Coast LLC.</p>
      <p>Kortų duomenys ir vaizdai – <a href="https://scryfall.com" target="_blank" rel="noopener noreferrer">Scryfall</a></p>
    </footer>
  </div>
</template>
