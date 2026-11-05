/**
 * The workspace sidebar: the mark, the menu grouped by product area (only what the current
 * role may open), and at the foot who is signed in. A real account shows its name, the role
 * the server gave it, its organisation and Sign out. The sandbox shows the demo-user switch
 * and a way out of the sandbox. On a phone the same sidebar opens as a drawer (AppShell).
 */
import { LogOut } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router'

import { Wordmark } from '@/components/Brand'
import { pick, useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { DASHBOARD, GROUPS, HOME, ROLE_NAMES, allowed, isActive, type NavItem } from './navigation'
import { useSession } from './session-context'

function Item({ item }: { item: NavItem }) {
  const { pathname } = useLocation()
  const t = useT()
  const active = isActive(item, pathname)
  return (
    <Link
      to={item.to}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'group flex min-h-12 items-center gap-3 rounded-[11px] px-3.5 text-[15.5px] no-underline transition-all duration-200 ease-out motion-reduce:transition-none',
        active
          ? 'bg-[#1d2d63] font-semibold text-white shadow-[inset_3px_0_0_#7fd1b9] hover:text-white'
          : 'font-medium text-[#b9c3e0] hover:translate-x-0.5 hover:bg-deep-2 hover:text-white motion-reduce:hover:translate-x-0',
      )}
    >
      <item.icon size={20} strokeWidth={1.8} aria-hidden="true" className={cn('shrink-0 transition-transform duration-200 group-hover:scale-110 motion-reduce:transition-none', active ? 'text-[#7fd1b9]' : '')} />
      <span className="min-w-0 flex-1">{t(item.label, item.labelBn)}</span>
    </Link>
  )
}

function AccountCard() {
  const { me, role, lang, signOut } = useSession()
  const navigate = useNavigate()
  const t = useT()
  return (
    <div className="mt-auto flex flex-col gap-1.5 rounded-[12px] border border-deep-line bg-deep-2 p-3">
      <span className="text-[14.5px] font-semibold text-white">{me?.display_name ?? me?.user_id}</span>
      <span className="text-[13px] text-[#b9c3e0]">{pick(ROLE_NAMES[role], lang)}</span>
      <span className="text-[12.5px] text-[#7d8bb5]">{me?.organization_name}</span>
      <button
        type="button"
        onClick={() => void signOut().then(() => navigate('/login'))}
        className="mt-1 inline-flex cursor-pointer items-center gap-1.5 self-start border-0 bg-transparent p-0 font-sans text-[13.5px] font-semibold text-[#b9c3e0] hover:text-white"
      >
        <LogOut size={15} aria-hidden="true" />
        {t('Sign out', 'সাইন আউট')}
      </button>
    </div>
  )
}

export function Sidebar() {
  const { role, isOwner } = useSession()
  const t = useT()
  return (
    <nav aria-label="CredLens" className="box-border flex h-full w-full flex-col gap-5 overflow-y-auto bg-deep px-3 py-5">
      <Link to={HOME[role]} className="px-3 no-underline" aria-label={t('CredLens home', 'CredLens হোম')}>
        <Wordmark size="sm" tone="light" />
      </Link>

      {allowed(DASHBOARD, role, isOwner) && (
        <div className="flex flex-col gap-0.5">
          <Item item={DASHBOARD} />
        </div>
      )}

      {GROUPS.map((group) => {
        const items = group.items.filter((i) => allowed(i, role, isOwner))
        if (!items.length) return null
        return (
          <div key={group.label} className="flex flex-col gap-0.5">
            <span className="px-3 pb-1 text-[11.5px] font-semibold tracking-[0.07em] text-[#7d8bb5] uppercase">{t(group.label, group.labelBn)}</span>
            {items.map((item) => (
              <Item key={item.to} item={item} />
            ))}
          </div>
        )
      })}

      <AccountCard />
    </nav>
  )
}
