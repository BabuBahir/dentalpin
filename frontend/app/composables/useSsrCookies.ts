/**
 * The cookie header SSR forwards to the backend (ADR 0023).
 *
 * The incoming request's ``cookie`` header is the starting point, but a
 * server-side refresh rotates the session mid-render: the refresh cookie
 * that came in is revoked the moment ``/auth/refresh`` answers. Every
 * later backend call in the *same* render must therefore use the merged
 * jar (incoming + the ``Set-Cookie`` values the refresh produced), or the
 * next call presents the revoked token and reuse detection burns the
 * family. The merged header lives on ``event.context`` so it is
 * per-request and visible to every composable, however early it was
 * created.
 */
const CONTEXT_KEY = 'dpCookieHeader'

/** Overlay ``Set-Cookie`` values onto a cookie header. */
export function mergeCookieHeader(incoming: string | undefined, setCookies: string[]): string {
  const jar = new Map<string, string>()
  for (const part of (incoming || '').split(';')) {
    const [k, ...v] = part.trim().split('=')
    if (k) jar.set(k, v.join('='))
  }
  for (const sc of setCookies) {
    const [pair] = sc.split(';')
    const [k, ...v] = (pair || '').trim().split('=')
    if (k) jar.set(k, v.join('='))
  }
  return Array.from(jar, ([k, v]) => `${k}=${v}`).join('; ')
}

export function useSsrCookies() {
  /** Current cookie header to forward (server only; ``undefined`` on the client). */
  function cookieHeader(): string | undefined {
    if (!import.meta.server) return undefined
    const event = useRequestEvent()
    const stored = event?.context[CONTEXT_KEY] as string | undefined
    if (stored !== undefined) return stored
    return useRequestHeaders(['cookie']).cookie
  }

  /** Headers object carrying the forwarded cookie (empty on the client). */
  function cookieHeaders(): Record<string, string> {
    const c = cookieHeader()
    return c ? { cookie: c } : {}
  }

  /** Record rotated cookies for the rest of this render and relay them to the browser. */
  function applySetCookies(setCookies: string[]): void {
    if (!import.meta.server || setCookies.length === 0) return
    const event = useRequestEvent()
    if (!event) return
    event.context[CONTEXT_KEY] = mergeCookieHeader(cookieHeader(), setCookies)
    for (const c of setCookies) appendResponseHeader(event, 'set-cookie', c)
  }

  return { cookieHeader, cookieHeaders, applySetCookies }
}
