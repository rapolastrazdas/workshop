import { reactive } from 'vue'

export const notice = reactive({ message: '', kind: 'info' as 'info' | 'error', path: '' })
let timer: ReturnType<typeof setTimeout> | undefined

export function dismissNotice() {
  clearTimeout(timer)
  notice.message = ''
  notice.path = ''
}

export function showNotice(message: string, path = window.location.pathname, kind: 'info' | 'error' = 'info') {
  dismissNotice()
  if (!message) return
  notice.message = message
  notice.path = path
  notice.kind = kind
  timer = setTimeout(dismissNotice, 5000)
}

export function clearNoticeOnNavigation(path: string) {
  if (notice.message && notice.path !== path) dismissNotice()
}
