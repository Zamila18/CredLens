/**
 * Sidebar (Sidebar.dc.html): logo, Work and Trust menus, data source, the language of
 * the whole dashboard and the demo role switch.
 *
 * - Items the current role may not open are hidden (docs/API_NOTES.md, "Who may call what").
 * - The data source is read-only: the API picks it from its config.
 * - The role switch sets the X-Demo-Token header. It is a demo, not a login.
 */
import { NavLink, useLocation } from 'react-router'

import type { Health, QueueItem, Role } from '@/api/types'
import { DEMO_USERS, type DemoUser } from '@/api/types'
import { useApi } from '@/api/useApi'
import { LensMark } from '@/components/icons'
import { Segmented } from '@/components/Segmented'
import { count } from '@/lib/format'
import { MODE_TEXT, pick, useT } from '@/lib/i18n'
import { hasQueue } from '@/lib/modes'
import { cn } from '@/lib/utils'
import { useSession, type Lang } from './session-context'

type Item = {
  to: string
  label: string
  labelBn: string
  /** Roles that may open the page; all roles when left out. */
  roles?: Role[]
  adminTag?: boolean
  /** Only shown when the data mode has a review queue. */
  needsQueue?: boolean
  badge?: boolean
}

const WORK: Item[] = [
  { to: '/', label: 'Review queue', labelBn: 'পর্যালোচনার তালিকা', needsQueue: true, badge: true },
  { to: '/decisions', label: 'Decision log', labelBn: 'সিদ্ধান্তের খাতা' },
  { to: '/portfolio', label: 'Portfolio', labelBn: 'পোর্টফোলিও' },
]

const TRUST: Item[] = [
  { to: '/model', label: 'Model card', labelBn: 'মডেল কার্ড' },
  { to: '/consent', label: 'Consent', labelBn: 'অনুমতি' },
  { to: '/audit', label: 'Audit log', labelBn: 'অডিট লগ', roles: ['admin'], adminTag: true },
  { to: '/admin/import', label: 'Data import', labelBn: 'ডেটা আমদানি', roles: ['admin'], adminTag: true },
]

const ROLE_LABELS: Record<DemoUser, { en: string; bn: string }> = {
  'officer-1': { en: 'Officer 1', bn: 'কর্মকর্তা ১' },
  'officer-2': { en: 'Officer 2', bn: 'কর্মকর্তা ২' },
  'admin-1': { en: 'Admin', bn: 'অ্যাডমিন' },
  'viewer-1': { en: 'Viewer', bn: 'দর্শক' },
}

function GroupLabel({ children }: { children: string }) {
  return <span className="px-2.5 pb-1.5 text-[11px] tracking-[.08em] text-night-label uppercase">{children}</span>
}

function NavItem({ item, badge }: { item: Item; badge?: number }) {
  const { pathname } = useLocation()
  const t = useT()
  // A merchant page belongs to the review queue.
  const forceActive = item.to === '/' && pathname.startsWith('/merchants/')
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) =>
        cn(
          'flex min-h-6 items-center justify-between gap-2 rounded-[9px] p-2.5 text-sm no-underline',
          isActive || forceActive
            ? 'bg-night-active font-semibold text-white shadow-[inset_3px_0_0_#E0A44A] hover:text-white'
            : 'font-medium text-night-text hover:bg-night-2 hover:text-white',
        )
      }
      aria-current={forceActive ? 'page' : undefined}
    >
      <span>{t(item.label, item.labelBn)}</span>
      {badge !== undefined && <span className="font-mono text-xs text-night-text tabular">{count(badge)}</span>}
      {item.adminTag && <span className="rounded-md border border-[#3A4E47] px-1.5 py-px text-[11px] text-night-soft">{t('admin', 'অ্যাডমিন')}</span>}
    </NavLink>
  )
}

export function Sidebar() {
  const { user, role, setUser, lang, setLang } = useSession()
  const t = useT()
  const health = useApi<Health>('/health')
  const mode = health.data?.data_mode
  const queue = useApi<QueueItem[]>(hasQueue(mode) ? '/merchants' : null)
  const pending = queue.data?.filter((m) => m.status === 'pending').length

  const visible = (item: Item) => (!item.roles || item.roles.includes(role)) && (!item.needsQueue || hasQueue(mode))

  return (
    <nav
      aria-label="CredLens"
      className="box-border flex w-full flex-col gap-7 bg-night px-4 py-6 text-night-hi lg:sticky lg:top-0 lg:h-screen lg:overflow-y-auto"
    >
      <NavLink to="/" className="flex items-center gap-2.5 px-2 text-white no-underline hover:text-white">
        <LensMark />
        <span className="flex flex-col leading-[1.1]">
          <span className="text-[19px] font-bold tracking-[-0.01em]">CredLens</span>
          <span className="text-[11px] tracking-[.06em] text-night-soft uppercase">{t('Merchant readiness', 'মার্চেন্টের প্রস্তুতি')}</span>
        </span>
      </NavLink>

      <div className="flex flex-col gap-1">
        <GroupLabel>{t('Work', 'কাজ')}</GroupLabel>
        {WORK.filter(visible).map((item) => (
          <NavItem key={item.to} item={item} badge={item.badge ? pending : undefined} />
        ))}
      </div>

      <div className="flex flex-col gap-1">
        <GroupLabel>{t('Trust', 'আস্থা')}</GroupLabel>
        {TRUST.filter(visible).map((item) => (
          <NavItem key={item.to} item={item} />
        ))}
      </div>

      <div className="flex flex-col gap-2 px-2.5">
        <span className="text-[11px] tracking-[.08em] text-night-label uppercase">{t('Data source', 'ডেটার উৎস')}</span>
        <div className="flex min-h-11 items-center rounded-lg border border-night-line bg-night-2 px-2.5 text-[13px] text-white">
          {mode ? (
            <span>
              <span className="font-mono">{mode}</span> · {pick(MODE_TEXT[mode], lang)}
            </span>
          ) : (
            <span className="text-night-soft">{t('Waiting for the API…', 'API-র জন্য অপেক্ষা…')}</span>
          )}
        </div>
        <span className="text-xs leading-[17px] text-night-soft">
          {t(
            'Set in the API config. Public modes show only what their data supports.',
            'API-র কনফিগে ঠিক করা। পাবলিক ডেটা শুধু ততটুকু দেখায় যতটুকু তার ডেটায় আছে।',
          )}
        </span>
      </div>

      <div className="flex flex-col gap-2 px-2.5">
        <span className="text-[11px] tracking-[.08em] text-night-label uppercase">
          Language · <span className="font-bn normal-case">ভাষা</span>
        </span>
        <Segmented<Lang>
          tone="dark"
          label="Language / ভাষা"
          value={lang}
          onChange={setLang}
          options={[
            { value: 'en', label: 'English' },
            { value: 'bn', label: <span className="font-bn">বাংলা</span> },
          ]}
        />
      </div>

      <div className="mt-auto flex flex-col gap-2 px-2.5">
        <span className="text-[11px] tracking-[.08em] text-night-label uppercase">{t('Demo role', 'ডেমো ভূমিকা')}</span>
        <Segmented<DemoUser>
          tone="dark"
          label={t('Demo role', 'ডেমো ভূমিকা')}
          value={user}
          onChange={setUser}
          options={DEMO_USERS.map((u) => ({ value: u, label: pick(ROLE_LABELS[u], lang) }))}
        />
        <span className="text-xs leading-[17px] text-night-soft">
          {t('Signed in as', 'ব্যবহারকারী:')} <span className="font-mono text-night-hi">{user}</span>.{' '}
          {t('A demo role switch, not a login.', 'এটি ডেমোর ভূমিকা বদল, লগইন নয়।')}
        </span>
      </div>
    </nav>
  )
}
