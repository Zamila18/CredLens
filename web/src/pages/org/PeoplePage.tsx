/**
 * People: everyone in the company (GET /org/employees). The owner Credit Officer can also give
 * a person a one-time code to set a new password (the reset) and disable an account. New people
 * are not added here: they register themselves with an invitation code (Invitation codes page).
 */
import { KeyRound, UserX } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { api } from '@/api/client'
import type { EmployeeOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { ROLE_NAMES } from '@/app/navigation'
import { useSession } from '@/app/session-context'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Notice } from '@/components/Notice'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtDate } from '@/lib/format'
import { pick, useLang, useT } from '@/lib/i18n'

type Reset = { employee: EmployeeOut; setup_code: string; expires_at: string }

export function PeoplePage() {
  const t = useT()
  const lang = useLang()
  const { user, isOwner } = useSession()
  const people = useApi<EmployeeOut[]>('/org/employees', undefined, { noCache: true })
  const [reset, setReset] = useState<Reset | null>(null)
  const [disabling, setDisabling] = useState<EmployeeOut | null>(null)
  const code = useSubmit<Reset>()
  const disable = useSubmit<EmployeeOut>()

  return (
    <Page>
      <PageHeader
        title={t('People', 'সদস্য')}
        description={t(
          'Everyone in your company and what each may do. A role is set by the invitation code the person joined with and is checked on the server for every action.',
          'আপনার প্রতিষ্ঠানের সবাই এবং প্রত্যেকে কী করতে পারেন। ভূমিকা ঠিক হয় যে আমন্ত্রণ কোডে যোগ দিয়েছেন তা দিয়ে, আর সার্ভার প্রতিটি কাজে তা যাচাই করে।',
        )}
        aside={
          isOwner ? (
            <Link to="/app/invitations" className="no-underline">
              <Button>{t('Invite someone', 'কাউকে আমন্ত্রণ করুন')}</Button>
            </Link>
          ) : undefined
        }
      />
      {reset && (
        <Notice tone="success" title={t(`One-time code for ${reset.employee.full_name}`, `${reset.employee.full_name}-এর একবারের কোড`)}>
          <span className="flex flex-col gap-2">
            <span className="w-fit rounded-[10px] border border-mint-line bg-white px-3 py-1.5 font-mono text-[20px] font-semibold tracking-[0.08em] text-ink">{reset.setup_code}</span>
            <span>
              {t(
                'Give it to the person. They open Sign in → “Use the one-time code”, enter their email, this code and a new password. It works once and is not shown again.',
                'কোডটি ব্যক্তিকে দিন। তিনি সাইন ইন → “একবারের কোড ব্যবহার করুন” খুলে ইমেইল, এই কোড ও নতুন পাসওয়ার্ড দেবেন। এটি একবারই কাজ করে, আর দেখানো হবে না।',
              )}
            </span>
          </span>
        </Notice>
      )}
      {people.error ? (
        <ErrorCallout error={people.error} />
      ) : !people.data ? (
        <LoadingState title={t('Loading people…', 'সদস্যরা আসছে…')} />
      ) : people.data.length === 0 ? (
        <EmptyState title={t('No one yet', 'এখনও কেউ নেই')} text="" />
      ) : (
        <ul className="m-0 flex list-none flex-col overflow-hidden rounded-card border border-card-line bg-card p-0">
          {people.data.map((p) => (
            <li key={p.user_id} className="grid gap-2 border-t border-line px-4 py-3 first:border-t-0 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1fr)_auto] md:items-center">
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-[15px] font-semibold text-ink">
                  {p.full_name}
                  {p.user_id === user && t(' (you)', ' (আপনি)')}
                </span>
                <span className="truncate text-[13px] text-muted-2">{p.email ?? p.mobile}</span>
                <span className="truncate text-[13px] text-muted-2">{[p.job_title, p.department].filter(Boolean).join(' · ')}</span>
              </span>
              <span className="text-[14px] text-ink-2">
                {pick(ROLE_NAMES[p.role as keyof typeof ROLE_NAMES], lang)}
                {p.is_owner && <span className="ml-1 font-semibold text-lens-dark">· {t('owner', 'মালিক')}</span>}
                {p.employee_id && <span className="block text-[12.5px] text-muted-2">ID {p.employee_id}</span>}
              </span>
              <span className="text-[13.5px]">
                {p.status === 'disabled' ? (
                  <span className="font-semibold text-muted-2">{t('Disabled', 'বন্ধ')}</span>
                ) : (
                  <span className="font-semibold text-lens-dark">{t('Active', 'সক্রিয়')}</span>
                )}
                <span className="block text-[12.5px] text-muted-2">{t('Joined', 'যোগ দিয়েছেন')} {fmtDate(p.registered_at)}</span>
              </span>
              {isOwner && p.status === 'active' && (
                <span className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={code.pending}
                    onClick={() => void code.submit(() => api<Reset>(`/org/employees/${encodeURIComponent(p.user_id)}/reset-code`, { method: 'POST' })).then((r) => r && setReset(r))}
                  >
                    <KeyRound size={15} aria-hidden="true" />
                    {t('Reset password', 'পাসওয়ার্ড রিসেট')}
                  </Button>
                  {p.user_id !== user && (
                    <Button size="sm" variant="ghost" onClick={() => setDisabling(p)}>
                      <UserX size={15} aria-hidden="true" />
                      {t('Disable', 'বন্ধ করুন')}
                    </Button>
                  )}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {code.error && <ErrorCallout error={code.error} />}
      <ConfirmDialog
        open={disabling !== null}
        onOpenChange={(open) => !open && setDisabling(null)}
        title={t(`Disable ${disabling?.full_name ?? ''}?`, `${disabling?.full_name ?? ''}-কে বন্ধ করবেন?`)}
        confirmLabel={t('Disable', 'বন্ধ করুন')}
        pending={disable.pending}
        onConfirm={() =>
          void disable
            .submit(() => api<EmployeeOut>(`/org/employees/${encodeURIComponent(disabling!.user_id)}/disable`, { method: 'POST' }))
            .then(() => {
              setDisabling(null)
              people.reload()
            })
        }
      >
        {t('They are signed out at once and cannot sign in again. Their shops are unassigned. Everything they recorded stays.', 'তাঁরা সঙ্গে সঙ্গে সাইন আউট হবেন, আর সাইন ইন করতে পারবেন না। তাঁদের দোকান বণ্টন থেকে সরবে। তাঁরা যা রেখেছেন সব থাকবে।')}
      </ConfirmDialog>
    </Page>
  )
}
