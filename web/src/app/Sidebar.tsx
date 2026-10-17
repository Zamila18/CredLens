/**
 * Sidebar (approved design: 00-design-system.png "Navigation", 01-home-desktop.png).
 *
 * The wordmark, Home, the Work and Trust menus, the data source and the demo role.
 * - Items the current role may not open are hidden (docs/API_NOTES.md, "Who may call what");
 *   the routes are guarded too (RequireRole), so hiding is not the only protection.
 * - Only the current page is highlighted. A merchant page belongs to the review queue;
 *   the consent demo belongs to Consent.
 * - The data source is read-only: the API picks it from its config.
 * - The role switch sets the X-Demo-Token header. It is a demo, not a login.
 * On a phone the same sidebar opens as a drawer from the menu button (AppShell).
 */
import type { LucideIcon } from 'lucide-react'
import {
  ChartNoAxesColumn,
  ClipboardList,
  Database,
  FileCheck2,
  House,
  NotebookText,
  ScrollText,
  ShieldCheck,
  Upload,
} from 'lucide-react'
import { NavLink, useLocation } from 'react-router'

import type { Health, QueueItem, Role } from '@/api/types'
import { DEMO_USERS, type DemoUser } from '@/api/types'
import { useApi } from '@/api/useApi'
import { count } from '@/lib/format'
import { MODE_TEXT, pick, useT } from '@/lib/i18n'
import { hasQueue } from '@/lib/modes'
import { cn } from '@/lib/utils'
import { useSession } from './session-context'

type Item = {
  to: string
  label: string
  labelBn: string
  icon: LucideIcon
  /** Roles that may open the page; all roles when left out. */
  roles?: Role[]
  /** Only shown when the data mode has a review queue. */
  needsQueue?: boolean
  badge?: boolean
  /** Other addresses that belong to this item (merchant pages belong to the queue). */
  alsoActive?: string[]
}

const HOME: Item = { to: '/', label: 'Home', labelBn: 'হোম', icon: House }

const WORK: Item[] = [
  {
    to: '/queue',
    label: 'Review queue',
    labelBn: 'পর্যালোচনার তালিকা',
    icon: ClipboardList,
    needsQueue: true,
    badge: true,
    alsoActive: ['/merchants/'],
  },
  { to: '/decisions', label: 'Decision log', labelBn: 'সিদ্ধান্তের খাতা', icon: NotebookText },
  { to: '/portfolio', label: 'Portfolio', labelBn: 'পোর্টফোলিও', icon: ChartNoAxesColumn },
]

const TRUST: Item[] = [
  { to: '/model', label: 'Model card', labelBn: 'মডেল কার্ড', icon: ShieldCheck },
  { to: '/consent', label: 'Consent', labelBn: 'অনুমতি', icon: FileCheck2, alsoActive: ['/demo/consent'] },
  { to: '/audit', label: 'Audit log', labelBn: 'অডিট লগ', icon: ScrollText, roles: ['admin'] },
  { to: '/admin/import', label: 'Data import', labelBn: 'ডেটা আমদানি', icon: Upload, roles: ['admin'] },
]

const ROLE_LABELS: Record<DemoUser, { en: string; bn: string }> = {
  'officer-1': { en: 'Officer 1', bn: 'কর্মকর্তা ১' },
  'officer-2': { en: 'Officer 2', bn: 'কর্মকর্তা ২' },
  'admin-1': { en: 'Admin', bn: 'অ্যাডমিন' },
  'viewer-1': { en: 'Viewer', bn: 'দর্শক' },
}

function GroupLabel({ children }: { children: string }) {
  return <span className="px-3 pb-1 text-[13px] font-medium text-muted-2">{children}</span>
}

function NavItem({ item, badge }: { item: Item; badge?: number }) {
  const { pathname } = useLocation()
  const t = useT()
  const Icon = item.icon
  const also = item.alsoActive?.some((prefix) => pathname.startsWith(prefix)) ?? false
  return (
    <NavLink
      to={item.to}
      end
      className={({ isActive }) =>
        cn(
          'flex min-h-11 items-center gap-3 rounded-[10px] px-3 text-[15px] no-underline transition-colors',
          isActive || also
            ? 'bg-mint font-semibold text-lens-dark hover:text-lens-dark'
            : 'font-medium text-ink-2 hover:bg-night-2 hover:text-ink',
        )
      }
      aria-current={also ? 'page' : undefined}
    >
      <Icon size={19} strokeWidth={1.8} aria-hidden="true" className="shrink-0" />
      <span className="min-w-0 flex-1">{t(item.label, item.labelBn)}</span>
      {badge !== undefined && (
        <span
          className="rounded-full bg-mint px-2 py-0.5 font-mono text-xs text-lens-dark tabular"
          aria-label={t(`${badge} waiting`, `${badge} অপেক্ষমাণ`)}
        >
          {count(badge)}
        </span>
      )}
    </NavLink>
  )
}

export function Sidebar() {
  const { user, role, setUser, lang } = useSession()
  const t = useT()
  const health = useApi<Health>('/health')
  const mode = health.data?.data_mode
  const queue = useApi<QueueItem[]>(hasQueue(mode) ? '/merchants' : null)
  const pending = queue.data?.filter((m) => m.status === 'pending').length

  const visible = (item: Item) => (!item.roles || item.roles.includes(role)) && (!item.needsQueue || hasQueue(mode))

  return (
    <nav aria-label="CredLens" className="box-border flex h-full w-full flex-col gap-6 overflow-y-auto bg-white px-4 py-6">
      <NavLink to="/" className="flex flex-col px-3 text-ink no-underline hover:text-ink">
        <span className="font-display text-[28px] leading-8 font-bold tracking-[-0.02em]">CredLens</span>
        <span className="text-[13px] text-muted-2">{t('Merchant readiness', 'মার্চেন্টের প্রস্তুতি')}</span>
      </NavLink>

      <div className="flex flex-col gap-1">
        <NavItem item={HOME} />
      </div>

      <div className="flex flex-col gap-1">
        <GroupLabel>{t('Work', 'কাজ')}</GroupLabel>
        {WORK.filter(visible).map((item) => (
          <NavItem key={item.to} item={item} badge={item.badge ? pending : undefined} />
        ))}
      </div>

      <div className="flex flex-col gap-1 border-t border-line pt-5">
        <GroupLabel>{t('Trust', 'আস্থা')}</GroupLabel>
        {TRUST.filter(visible).map((item) => (
          <NavItem key={item.to} item={item} />
        ))}
      </div>

      <div className="mt-auto flex flex-col gap-4 border-t border-line pt-5">
        <div className="flex flex-col gap-1 px-3">
          <span className="flex items-center gap-2 text-sm font-medium text-ink">
            <Database size={16} strokeWidth={1.8} aria-hidden="true" />
            {mode ? (
              <span>
                <span className="font-mono text-[13px]">{mode}</span> · {pick(MODE_TEXT[mode], lang)}
              </span>
            ) : (
              <span className="text-muted-2">{t('Waiting for the API…', 'API-র জন্য অপেক্ষা…')}</span>
            )}
          </span>
          <span className="text-xs leading-[17px] text-muted-2">
            {t(
              'Set in the API config. Public modes show only what their data supports.',
              'API-র কনফিগে ঠিক করা। পাবলিক ডেটা শুধু ততটুকু দেখায় যতটুকু তার ডেটায় আছে।',
            )}
          </span>
        </div>

        <div className="flex flex-col gap-1.5 px-3">
          <label htmlFor="demo-role" className="text-sm font-medium text-ink">
            {t('Demo role', 'ডেমো ভূমিকা')}
          </label>
          <select
            id="demo-role"
            value={user}
            onChange={(e) => setUser(e.target.value as DemoUser)}
            className="min-h-11 w-full rounded-[10px] border border-control-line bg-white px-3 text-[15px] text-ink"
          >
            {DEMO_USERS.map((u) => (
              <option key={u} value={u}>
                {pick(ROLE_LABELS[u], lang)} ({u})
              </option>
            ))}
          </select>
          <span className="text-xs leading-[17px] text-muted-2">
            {t('A demo role switch, not a login.', 'এটি ডেমোর ভূমিকা বদল, লগইন নয়।')}
          </span>
        </div>
      </div>
    </nav>
  )
}
