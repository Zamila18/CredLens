/**
 * The workspace menu: product areas, their pages, and which roles may open each.
 * The sidebar and the phone tab bar both read it. Hiding a page is not the protection:
 * RequireRole guards the address and the API checks every call.
 *
 * Roles: credit_officer (the company's first officer is its owner), records_officer (the
 * Records Desk, which processes receipts), merchant (a shop owner, on their own portal), auditor,
 * and platform_admin (CredLens staff; platform pages only).
 */
import type { LucideIcon } from 'lucide-react'
import {
  Building2,
  ClipboardList,
  FileStack,
  FilePlus2,
  Flag,
  HandCoins,
  KeyRound,
  LayoutDashboard,
  NotebookText,
  Receipt,
  ScrollText,
  Settings2,
  ShieldCheck,
  Store,
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

/** The company's decision makers and reviewers. */
const READERS: Role[] = ['credit_officer', 'auditor']

export const DASHBOARD: NavItem = { to: '/app', label: 'Overview', labelBn: 'সারসংক্ষেপ', icon: LayoutDashboard, roles: READERS }

const MERCHANTS: NavItem = { to: '/app/merchants', label: 'Merchants', labelBn: 'মার্চেন্ট', icon: Store, roles: READERS, alsoActive: ['/app/merchants/'] }
const REGISTRATIONS: NavItem = { to: '/app/registrations', label: 'Add a merchant', labelBn: 'মার্চেন্ট যোগ করুন', icon: FilePlus2, roles: ['credit_officer'], alsoActive: ['/app/registrations/'] }
const APPLICATIONS: NavItem = { to: '/app/applications', label: 'Loan applications', labelBn: 'ঋণের আবেদন', icon: FileStack, roles: READERS }
const DECISIONS: NavItem = { to: '/app/decisions', label: 'Decisions', labelBn: 'সিদ্ধান্ত', icon: NotebookText, roles: READERS }
const TEAM: NavItem = { to: '/app/team', label: 'Team', labelBn: 'দল', icon: Users, roles: ['credit_officer'] }
const INVITATIONS: NavItem = { to: '/app/invitations', label: 'Invitation codes', labelBn: 'আমন্ত্রণ কোড', icon: KeyRound, roles: ['credit_officer'], ownerOnly: true }
const COMPANY: NavItem = { to: '/app/company', label: 'Company', labelBn: 'প্রতিষ্ঠান', icon: Building2, roles: ['credit_officer'] }
const AUDIT: NavItem = { to: '/app/audit', label: 'Audit log', labelBn: 'অডিট লগ', icon: ScrollText, roles: ['credit_officer', 'auditor'] }
const MODEL: NavItem = { to: '/app/model', label: 'How scores work', labelBn: 'স্কোর কীভাবে হয়', icon: ShieldCheck, roles: READERS }
const SETTINGS: NavItem = { to: '/app/settings', label: 'Settings', labelBn: 'সেটিংস', icon: Settings2 }
const PLATFORM_ORGS: NavItem = { to: '/app/platform', label: 'Companies', labelBn: 'প্রতিষ্ঠানসমূহ', icon: Building2, roles: ['platform_admin'] }

const RECEIPTS: NavItem = { to: '/app/receipts', label: 'Receipts', labelBn: 'রসিদ', icon: Receipt, roles: ['records_officer'], alsoActive: ['/app/receipts/'] }
const REPORTS: NavItem = { to: '/app/reports', label: 'Merchant reports', labelBn: 'ব্যবসায়ীর অভিযোগ', icon: Flag, roles: ['records_officer'] }

const MY_RECORDS: NavItem = { to: '/app/portal', label: 'My records', labelBn: 'আমার হিসাব', icon: ClipboardList, roles: ['merchant'] }
const MY_REPORTS: NavItem = { to: '/app/portal/reports', label: 'My reports', labelBn: 'আমার অভিযোগ', icon: Flag, roles: ['merchant'] }
const APPLY: NavItem = { to: '/app/portal/apply', label: 'Apply for a loan', labelBn: 'ঋণের আবেদন', icon: HandCoins, roles: ['merchant'] }

export const GROUPS: NavGroup[] = [
  { label: 'Platform', labelBn: 'প্ল্যাটফর্ম', items: [PLATFORM_ORGS] },
  { label: 'Work', labelBn: 'কাজ', items: [MERCHANTS, REGISTRATIONS, APPLICATIONS, DECISIONS] },
  { label: 'Receipts', labelBn: 'রসিদ', items: [RECEIPTS, REPORTS] },
  { label: 'My shop', labelBn: 'আমার দোকান', items: [MY_RECORDS, MY_REPORTS, APPLY] },
  { label: 'Company', labelBn: 'প্রতিষ্ঠান', items: [TEAM, INVITATIONS, COMPANY, MODEL, AUDIT] },
  { label: 'Account', labelBn: 'অ্যাকাউন্ট', items: [SETTINGS] },
]

/** The places each role uses most, for the phone tab bar. */
export const PHONE_TABS: Record<Role, NavItem[]> = {
  platform_admin: [PLATFORM_ORGS, SETTINGS],
  credit_officer: [DASHBOARD, MERCHANTS, APPLICATIONS, SETTINGS],
  records_officer: [RECEIPTS, REPORTS, SETTINGS],
  merchant: [MY_RECORDS, APPLY, MY_REPORTS],
  auditor: [AUDIT, DECISIONS, MERCHANTS, DASHBOARD],
}

/** Where each role starts after signing in. */
export const HOME: Record<Role, string> = {
  platform_admin: '/app/platform',
  credit_officer: '/app',
  records_officer: '/app/receipts',
  merchant: '/app/portal',
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
  if (item.to === '/app/portal') return pathname === '/app/portal'
  return pathname === item.to || (item.alsoActive?.some((p) => pathname.startsWith(p)) ?? false)
}

/** Every role's name, for the account line in the shell. */
export const ROLE_NAMES: Record<Role, { en: string; bn: string }> = {
  platform_admin: { en: 'Platform administrator', bn: 'প্ল্যাটফর্ম অ্যাডমিন' },
  credit_officer: { en: 'Credit officer', bn: 'ক্রেডিট অফিসার' },
  records_officer: { en: 'Records Desk', bn: 'রেকর্ড ডেস্ক' },
  merchant: { en: 'Merchant', bn: 'ব্যবসায়ী' },
  auditor: { en: 'Auditor', bn: 'অডিটর' },
}
