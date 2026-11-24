import { reactive } from 'vue'
import { dismissNotice, showNotice } from './notices'

type User = { id: number; email: string }
type Session = { access_token: string; expires_at: number; user: User }
const STORAGE_KEY = 'workshop.session'
const EXPIRED_MESSAGE = 'Jūsų sesija baigėsi. Prisijunkite iš naujo.'
let timer: ReturnType<typeof setTimeout> | undefined

// Session storage keeps sign-in across reloads within this browser tab.
function readSession(): Session | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null')
    return value && typeof value.access_token === 'string' &&
      Number.isFinite(value.expires_at) && typeof value.user?.email === 'string' ? value : null
  } catch {
    return null
  }
}

export const auth = reactive({
  session: readSession() as Session | null,
})

export function clearSession() {
  dismissNotice()
  clearTimeout(timer)
  auth.session = null
  sessionStorage.removeItem(STORAGE_KEY)
}

export function expireSession() {
  if (!auth.session) return
  clearSession()
  showNotice(EXPIRED_MESSAGE, '/prisijungimas')
  window.dispatchEvent(new Event('workshop:session-expired'))
}

export function scheduleExpiry() {
  clearTimeout(timer)
  if (!auth.session) return
  const remaining = auth.session.expires_at * 1000 - Date.now()
  if (remaining <= 0) expireSession()
  else timer = setTimeout(expireSession, Math.min(remaining, 2_147_483_647))
}

export function saveSession(session: Session) {
  auth.session = session
  dismissNotice()
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  scheduleExpiry()
}

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === 'string' ? detail : 'Nepavyko atlikti veiksmo. Bandykite dar kartą.')
  }
}

export async function api<T>(path: string, options: RequestInit = {}, authenticated = true): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (authenticated && auth.session) headers.set('Authorization', `Bearer ${auth.session.access_token}`)
  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...options, headers, cache: 'no-store' })
  } catch {
    throw new Error('Nepavyko susisiekti su serveriu. Patikrinkite ryšį ir bandykite dar kartą.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    if (response.status === 401 && authenticated) expireSession()
    throw new ApiError(response.status, body.detail)
  }
  return response.status === 204 ? undefined as T : response.json()
}

export async function authenticate(path: 'login' | 'register', data: Record<string, string>) {
  const session = await api<Session>(`/auth/${path}`, {
    method: 'POST', body: JSON.stringify(data),
  }, false)
  saveSession(session)
}

export async function verifySession(): Promise<boolean> {
  if (!auth.session) return false
  if (auth.session.expires_at * 1000 <= Date.now()) {
    expireSession()
    return false
  }
  const user = await api<User>('/auth/me')
  if (!auth.session) return false
  auth.session.user = user
  scheduleExpiry()
  return true
}

window.addEventListener('focus', () => {
  if (auth.session && auth.session.expires_at * 1000 <= Date.now()) expireSession()
})
