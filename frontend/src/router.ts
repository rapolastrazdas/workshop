import { createRouter, createWebHistory } from 'vue-router'
import { ApiError, auth, scheduleExpiry, verifySession } from './auth'
import AuthView from './views/AuthView.vue'
import HomeView from './views/HomeView.vue'
import DecksView from './views/DecksView.vue'
import DeckView from './views/DeckView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/registracija', alias: '/register', name: 'register', component: AuthView, props: { mode: 'register' } },
    { path: '/prisijungimas', alias: '/login', name: 'login', component: AuthView, props: { mode: 'login' } },
    { path: '/mano-kalades', alias: '/decks', name: 'decks', component: DecksView, meta: { requiresAuth: true } },
    { path: '/kalades/:id', alias: '/decks/:id', name: 'deck', component: DeckView, meta: { requiresAuth: true } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  if (!to.meta.requiresAuth && !auth.session) return true
  try {
    const signedIn = await verifySession()
    if (!signedIn && auth.notice && to.name !== 'login') return { name: 'login' }
    if (to.meta.requiresAuth && !signedIn) return { name: 'login' }
    if (signedIn && ['login', 'register'].includes(String(to.name))) return { name: 'decks' }
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      if (to.meta.requiresAuth) return { name: 'login' }
    } else {
      auth.notice = error instanceof Error ? error.message : 'Nepavyko patikrinti sesijos.'
      if (to.meta.requiresAuth) return { name: 'login' }
    }
  }
  return true
})

window.addEventListener('workshop:session-expired', () => {
  void router.replace({ name: 'login' })
})

void router.isReady().then(scheduleExpiry)
