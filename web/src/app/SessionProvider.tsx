/**
 * Holds the demo session and remembers it in the browser between visits.
 * Switching the demo user changes the X-Demo-Token sent with every later call.
 */
import { useEffect, useMemo, useState, type ReactNode } from 'react'

import { setDemoUser } from '@/api/client'
import { DEMO_USERS, roleOf, type DemoUser } from '@/api/types'
import { readChoice, saveChoice } from '@/lib/storage'
import { SessionContext, type Lang, type Session } from './session-context'

const USER_KEY = 'credlens.demoUser'
const LANG_KEY = 'credlens.lang'

// Set the token before the first render, so the very first API call already carries it.
const initialUser = readChoice<DemoUser>(USER_KEY, DEMO_USERS, 'officer-1')
setDemoUser(initialUser)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<DemoUser>(initialUser)
  // `?lang=bn` (or `?lang=en`) in a link opens the dashboard in that language and keeps it.
  const [lang, setLangState] = useState<Lang>(() => {
    const asked = new URLSearchParams(window.location.search).get('lang')
    if (asked === 'en' || asked === 'bn') {
      saveChoice(LANG_KEY, asked)
      return asked
    }
    return readChoice<Lang>(LANG_KEY, ['en', 'bn'], 'en')
  })

  // The whole page follows the language switch: screen readers and the Bangla font
  // (index.css, html[lang='bn']) read it from <html lang>.
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const session = useMemo<Session>(
    () => ({
      user,
      role: roleOf(user),
      setUser: (next) => {
        setDemoUser(next)
        saveChoice(USER_KEY, next)
        setUserState(next)
      },
      lang,
      setLang: (next) => {
        saveChoice(LANG_KEY, next)
        setLangState(next)
      },
    }),
    [user, lang],
  )

  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>
}
