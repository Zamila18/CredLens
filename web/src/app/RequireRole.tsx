/**
 * Shows a page only to the roles that may open it. The API checks again on every
 * call; this just gives a clear message instead of a page full of errors.
 */
import type { ReactNode } from 'react'

import type { Role } from '@/api/types'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Page } from '@/components/Page'
import { useSession } from './session-context'

export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { role } = useSession()
  if (roles.includes(role)) return <>{children}</>
  return (
    <Page>
      <ErrorCallout error={{ status: 403, code: 'role_not_allowed', message: '' }} className="max-w-[640px]" />
    </Page>
  )
}
