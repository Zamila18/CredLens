/**
 * Who is using the application, as the server says, and the language of the screens.
 *
 * mode:
 * - "loading": asking the server (GET /auth/me) on first load;
 * - "signed_out": nobody; the workspace sends the browser to /login;
 * - "account": a signed-in account (session cookie). Role and company come from the server.
 */
import { createContext, useContext } from 'react'

import type { MeOut, Role } from '@/api/types'

export type Lang = 'en' | 'bn'
export type SessionMode = 'loading' | 'signed_out' | 'account'

export type Session = {
  mode: SessionMode
  /** What the server says about the caller; null while loading or signed out. */
  me: MeOut | null
  /** The caller's user id ('' when nobody), used to keep cached answers per person. */
  user: string
  /** The role the server gave the caller (never chosen in the browser). */
  role: Role
  /** The company's owner Credit Officer. */
  isOwner: boolean
  /** Sign in (sets the session cookie) or out. */
  signIn: (identifier: string, password: string) => Promise<MeOut>
  signOut: () => Promise<void>
  lang: Lang
  setLang: (lang: Lang) => void
}

export const SessionContext = createContext<Session | null>(null)

/** The current caller, role and language. Use inside <SessionProvider>. */
export function useSession(): Session {
  const session = useContext(SessionContext)
  if (!session) throw new Error('useSession must be used inside <SessionProvider>')
  return session
}
