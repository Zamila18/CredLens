/**
 * The workspace menu: product areas, their pages, and which roles may open each.
 * The sidebar and the phone tab bar both read it. Hiding a page is not the protection:
 * RequireRole guards the address and the API checks every call.
 *
 * Roles: credit_officer (the company's first officer is its owner), fsr (Field Sales
 * Representative), auditor, and platform_admin (CredLens staff; platform pages only).
 */
import type { LucideIcon } from 'lucide-react'
import {
  Building2,
  Cable,
  CalendarDays,
  Inbox,
  Scale,
  FileStack,
  FilePlus2,
  FolderInput,
  KeyRound,
  LayoutDashboard,
  MapPinned,
  NotebookText,
  ScanSearch,
  ScrollText,
  Settings2,
  ShieldCheck,
  Store,
  UserRoundCog,
  Users,
} from 'lucide-react'

import type { Role } from '@/api/types'

export type NavItem = {
  to: string
  label: string
  labelBn: string
  icon: LucideIcon
  /** Roles that may open the page; all roles when left out. */
  roles?: Role[]
  /** Only the company's owner Credit Officer sees this item. */
  ownerOnly?: boolean
  /** Other address prefixes that belong to this item. */
  alsoActive?: string[]
}

export type NavGroup = { label: string; labelBn: string; items: NavItem[] }

/** Everyone in a company except the FSR, who works on assigned shops only. */
const READERS: Role[] = ['credit_officer', 'auditor']

export const DASHBOARD: NavItem = { to: '/app', label: 'Overview', labelBn: 'সারসংক্ষেপ', icon: LayoutDashboard, roles: READERS }

const FIELD: NavItem = { to: '/app/field', label: 'Field work', labelBn: 'মাঠের কাজ', icon: MapPinned, roles: ['credit_officer', 'fsr'], alsoActive: ['/app/field/'] }
const MY_SHOPS: NavItem = { to: '/app/shops', label: 'My shops', labelBn: 'আমার দোকান', icon: CalendarDays, roles: ['fsr'], alsoActive: ['/app/shops/'] }
const SUBMISSIONS: NavItem = { to: '/app/submissions', label: 'Daily submissions', labelBn: 'দৈনিক জমা', icon: Inbox, roles: ['credit_officer', 'auditor'] }
const RANGE_POLICY: NavItem = { to: '/app/range-policy', label: 'Range policy', labelBn: 'পরিসীমা-নীতি', icon: Scale, roles: ['credit_officer'] }
const TEAM: NavItem = { to: '/app/team', label: 'People', labelBn: 'সদস্য', icon: Users, roles: ['credit_officer'] }
const INVITATIONS: NavItem = { to: '/app/invitations', label: 'Invitation codes', labelBn: 'আমন্ত্রণ কোড', icon: KeyRound, roles: ['credit_officer'], ownerOnly: true }
const COMPANY: NavItem = { to: '/app/company', label: 'Company profile', labelBn: 'প্রতিষ্ঠানের তথ্য', icon: Building2, roles: ['credit_officer'] }
const ASSIGNMENTS: NavItem = { to: '/app/assignments', label: 'Shop assignments', labelBn: 'দোকান বণ্টন', icon: UserRoundCog, roles: ['credit_officer'] }
const REGISTRATIONS: NavItem = { to: '/app/registrations', label: 'Registrations', labelBn: 'নিবন্ধন', icon: FilePlus2, roles: ['credit_officer'], alsoActive: ['/app/registrations/'] }
const MERCHANTS: NavItem = { to: '/app/merchants', label: 'Merchants', labelBn: 'মার্চেন্ট তালিকা', icon: Store, roles: READERS, alsoActive: ['/app/merchants/'] }
const APPLICATIONS: NavItem = { to: '/app/applications', label: 'Applications', labelBn: 'আবেদন', icon: FileStack, roles: READERS }
const DECISIONS: NavItem = { to: '/app/decisions', label: 'Decisions', labelBn: 'সিদ্ধান্ত', icon: NotebookText, roles: READERS }
const AUDIT: NavItem = { to: '/app/audit', label: 'Audit log', labelBn: 'অডিট লগ', icon: ScrollText, roles: ['credit_officer', 'auditor'] }
const SETTINGS: NavItem = { to: '/app/settings', label: 'Settings', labelBn: 'সেটিংস', icon: Settings2 }
const PLATFORM_ORGS: NavItem = { to: '/app/platform', label: 'Companies', labelBn: 'প্রতিষ্ঠানসমূহ', icon: Building2, roles: ['platform_admin'] }

export const GROUPS: NavGroup[] = [
  { label: 'Platform', labelBn: 'প্ল্যাটফর্ম', items: [PLATFORM_ORGS] },
  { label: 'Company', labelBn: 'প্রতিষ্ঠান', items: [TEAM, INVITATIONS, ASSIGNMENTS, COMPANY] },
  { label: 'Merchants', labelBn: 'মার্চেন্ট', items: [MY_SHOPS, REGISTRATIONS, SUBMISSIONS, FIELD, MERCHANTS] },
  { label: 'Credit', labelBn: 'ঋণ', items: [APPLICATIONS, DECISIONS, RANGE_POLICY] },
  {
    label: 'Evidence and insight',
    labelBn: 'প্রমাণ ও বিশ্লেষণ',
    items: [
      { to: '/app/sources', label: 'Data sources', labelBn: 'ডেটার উৎস', icon: Cable, roles: ['credit_officer'], alsoActive: ['/app/sources/'] },
      { to: '/app/quality', label: 'Data quality', labelBn: 'ডেটার মান', icon: ScanSearch, roles: READERS },
      { to: '/app/imports', label: 'Spreadsheet imports', labelBn: 'স্প্রেডশিট আমদানি', icon: FolderInput, roles: ['credit_officer'], alsoActive: ['/app/imports/'] },
      { to: '/app/model', label: 'Model information', labelBn: 'মডেলের তথ্য', icon: ShieldCheck, roles: READERS },
    ],
  },
  { label: 'Administration', labelBn: 'প্রশাসন', items: [AUDIT, SETTINGS] },
]

/** The places each role uses most, for the phone tab bar. */
export const PHONE_TABS: Record<Role, NavItem[]> = {
  platform_admin: [PLATFORM_ORGS, SETTINGS],
  credit_officer: [DASHBOARD, SUBMISSIONS, MERCHANTS, APPLICATIONS],
  fsr: [MY_SHOPS, FIELD, SETTINGS],
  auditor: [AUDIT, DECISIONS, MERCHANTS, DASHBOARD],
}

/** Where each role starts after signing in. */
export const HOME: Record<Role, string> = {
  platform_admin: '/app/platform',
  credit_officer: '/app',
  fsr: '/app/shops',
  auditor: '/app/audit',
}

export function allowed(item: NavItem, role: Role, isOwner = false): boolean {
  if (item.roles && !item.roles.includes(role)) return false
  if (item.ownerOnly && !isOwner) return false
  // The audit log is for the company's owner and for auditors.
  if (item.to === '/app/audit' && role === 'credit_officer' && !isOwner) return false
  return true
}

export function isActive(item: NavItem, pathname: string): boolean {
  if (item.to === '/app') return pathname === '/app' || pathname === '/app/'
  return pathname === item.to || (item.alsoActive?.some((p) => pathname.startsWith(p)) ?? false)
}

/** Every role's name, for the account line in the shell. */
export const ROLE_NAMES: Record<Role, { en: string; bn: string }> = {
  platform_admin: { en: 'Platform administrator', bn: 'প্ল্যাটফর্ম অ্যাডমিন' },
  credit_officer: { en: 'Credit officer', bn: 'ক্রেডিট অফিসার' },
  fsr: { en: 'Field Sales Representative', bn: 'ফিল্ড সেলস রিপ্রেজেন্টেটিভ' },
  auditor: { en: 'Auditor', bn: 'অডিটর' },
}
