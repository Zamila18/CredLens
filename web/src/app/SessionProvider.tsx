/**
 * Finds out who is using the application (GET /auth/me) and keeps the language choice.
 *
 * On first load the server is asked: if the browser holds a valid session cookie, that is the
 * session; otherwise nobody is signed in and the workspace sends them to /login. The role
 * always comes from the server.
 */
import { useEffect, useMemo, useState, type ReactNode } from 'react'

import { api } from '@/api/client'
import type { MeOut } from '@/api/types'
import { clearApiCache } from '@/api/useApi'
import { readChoice, saveChoice } from '@/lib/storage'
import { SessionContext, type Lang, type Session, type SessionMode } from './session-context'

const LANG_KEY = 'credlens.lang'

export function SessionProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<SessionMode>('loading')
  const [me, setMe] = useState<MeOut | null>(null)
  // `?lang=bn` (or `?lang=en`) in a link opens the application in that language and keeps it.
  const [lang, setLangState] = useState<Lang>(() => {
    const asked = new URLSearchParams(window.location.search).get('lang')
    if (asked === 'en' || asked === 'bn') {
      saveChoice(LANG_KEY, asked)
      return asked
    }
    return readChoice<Lang>(LANG_KEY, ['en', 'bn'], 'en')
  })

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  useEffect(() => {
    let alive = true
    api<MeOut>('/auth/me')
      .then((who) => {
        if (!alive) return
        setMe(who)
        setMode('account')
      })
      .catch(() => {
        if (!alive) return
        setMe(null)
        setMode('signed_out')
      })
    return () => {
      alive = false
    }
  }, [])

  const session = useMemo<Session>(
    () => ({
      mode,
      me,
      user: me?.user_id ?? '',
      role: (me?.role as Session['role']) ?? 'auditor',
      isOwner: me?.is_owner ?? false,
      signIn: async (identifier, password) => {
        const who = await api<MeOut>('/auth/login', { method: 'POST', json: { identifier, password } })
        clearApiCache()
        setMe(who)
        setMode('account')
        return who
      },
      signOut: async () => {
        try {
          await api('/auth/logout', { method: 'POST' })
        } finally {
          clearApiCache()
          setMe(null)
          setMode('signed_out')
        }
      },
      lang,
      setLang: (next) => {
        saveChoice(LANG_KEY, next)
        setLangState(next)
      },
    }),
    [mode, me, lang],
  )

  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>
}
