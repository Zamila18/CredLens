/**
 * The demo session: which demo user the sidebar picked, and the language of the whole
 * dashboard (English or Bangla). This is a demo role switch, not a login.
 */
import { createContext, useContext } from 'react'

import type { DemoUser, Role } from '@/api/types'

export type Lang = 'en' | 'bn'

export type Session = {
  user: DemoUser
  role: Role
  setUser: (user: DemoUser) => void
  lang: Lang
  setLang: (lang: Lang) => void
}

export const SessionContext = createContext<Session | null>(null)

/** The current demo user, role and language. Use inside <SessionProvider>. */
export function useSession(): Session {
  const session = useContext(SessionContext)
  if (!session) throw new Error('useSession must be used inside <SessionProvider>')
  return session
}
