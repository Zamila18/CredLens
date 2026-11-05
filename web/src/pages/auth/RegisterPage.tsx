/**
 * Register: a new company with its first Credit Officer, or join an existing company with an
 * invitation code (POST /auth/register/company and /auth/register/join).
 *
 * No second verification step: the person sets a password (12 characters, mixed case, digit,
 * symbol) and is signed in straight away, to the dashboard of their own company and role. A work email here is not verified; an invitation code only
 * proves the link to the company. The company and role of someone joining come from the
 * code, never from this form.
 */
import { Building2, UserPlus } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { ApiError, api } from '@/api/client'
import { HOME } from '@/app/navigation'
import { useSession } from '@/app/session-context'
import type { InvitationPreviewOut } from '@/api/types'
import { Field, Select, TextInput } from '@/components/form'
import { Notice } from '@/components/Notice'
import { Button } from '@/components/ui/button'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { AuthFrame } from './AuthFrame'

type Values = Record<string, string>
type Tab = 'company' | 'join'

const ORG_TYPES: [string, string, string][] = [
  ['bank', 'Bank', 'ব্যাংক'],
  ['nbfi', 'Non-bank financial institution', 'নন-ব্যাংক আর্থিক প্রতিষ্ঠান'],
  ['mfi', 'Microfinance institution', 'ক্ষুদ্রঋণ প্রতিষ্ঠান'],
  ['cooperative', 'Cooperative', 'সমবায়'],
  ['fintech_lender', 'Fintech lender', 'ফিনটেক ঋণদাতা'],
  ['distributor_lender', 'Distributor offering credit', 'ক্রেডিট দেওয়া ডিস্ট্রিবিউটর'],
  ['other', 'Other', 'অন্যান্য'],
]
/** The company form sends no invitation fields (the server refuses unknown ones). */
const companyBody = (values: Values): Values => {
  const { invitation_code: _code, role: _role, employee_id: _id, ...rest } = values
  return rest
}
const JOIN_KEYS = ['full_name', 'email', 'mobile', 'department', 'password', 'confirm_password', 'invitation_code', 'employee_id']
const joinBody = (values: Values, role: string): Values => ({ ...Object.fromEntries(JOIN_KEYS.filter((k) => values[k] !== undefined).map((k) => [k, values[k]])), role })
const NUMBER_REQUIRED = ['bank', 'nbfi', 'mfi', 'cooperative', 'fintech_lender']

export function RegisterPage() {
  const t = useT()
  const navigate = useNavigate()
  const { signIn } = useSession()
  const [params] = useSearchParams()
  const [tab, setTab] = useState<Tab>(params.get('code') ? 'join' : 'company')
  const [v, setV] = useState<Values>({ country: 'BD', invitation_code: params.get('code') ?? '' })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [pending, setPending] = useState(false)
  const [general, setGeneral] = useState<string | null>(null)
  const [previewed, setPreviewed] = useState<{ code: string; data: InvitationPreviewOut } | null>(null)

  const set = (key: string) => (e: { target: { value: string } }) => setV((old) => ({ ...old, [key]: e.target.value }))
  const text = (key: string, props: Record<string, unknown> = {}) => (
    <TextInput value={v[key] ?? ''} onChange={set(key)} {...props} />
  )

  // A valid code shows which company and role it opens, before anything is typed.
  const code = (v.invitation_code ?? '').trim()
  const ready = tab === 'join' && code.replace(/[^a-zA-Z0-9]/g, '').length >= 16
  useEffect(() => {
    if (!ready) return
    let alive = true
    api<InvitationPreviewOut>('/auth/invitations/preview', { query: { code } })
      .then((data) => alive && setPreviewed({ code, data }))
      .catch(() => alive && setPreviewed(null))
    return () => {
      alive = false
    }
  }, [ready, code])
  const preview = ready && previewed?.code === code ? previewed.data : null
  // The role the person says they have; a valid code suggests its own, and the server checks they match.
  const role = v.role || preview?.role || ''

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setPending(true)
    setErrors({})
    setGeneral(null)
    try {
      await api(tab === 'company' ? '/auth/register/company' : '/auth/register/join', { method: 'POST', json: tab === 'join' ? joinBody(v, role) : companyBody(v) })
      try {
        const who = await signIn(v.email, v.password)
        navigate(HOME[who.role as keyof typeof HOME] ?? '/app')
      } catch {
        navigate('/login?registered=1')
      }
    } catch (err) {
      if (err instanceof ApiError) {
        const fields = (err.facts as { fields?: Record<string, string> }).fields
        if (fields) setErrors(fields)
        setGeneral(err.status === 429 ? t('Too many attempts. Wait a few minutes and try again.', 'অনেকবার চেষ্টা হয়েছে। কয়েক মিনিট পর আবার চেষ্টা করুন।') : err.message)
      } else setGeneral(t('The API could not be reached.', 'API-তে পৌঁছানো যায়নি।'))
    } finally {
      setPending(false)
    }
  }

  const tabButton = (id: Tab, label: string, icon: React.ReactNode) => (
    <button
      type="button"
      role="tab"
      aria-selected={tab === id}
      onClick={() => {
        setTab(id)
        setErrors({})
        setGeneral(null)
      }}
      className={cn(
        'inline-flex min-h-11 flex-1 cursor-pointer items-center justify-center gap-2 rounded-[10px] border px-3 font-sans text-[14.5px] font-semibold',
        tab === id ? 'border-lens-dark bg-lens-dark text-white' : 'border-control-line bg-white text-ink-2 hover:border-lens',
      )}
    >
      {icon}
      {label}
    </button>
  )

  const err = (key: string) => errors[key] ?? null
  const orgType = v.org_type ?? ''
  const person = (
    <>
      <fieldset className="m-0 flex flex-col gap-4 border-0 p-0">
        <legend className="mb-1 p-0 text-[13px] font-semibold tracking-[0.06em] text-muted-2 uppercase">{t('About you', 'আপনার তথ্য')}</legend>
        <Field label={t('Full legal name', 'পূর্ণ নাম')} required error={err('full_name')}>{text('full_name', { autoComplete: 'name' })}</Field>
        <Field label={t('Work email', 'অফিসের ইমেইল')} required error={err('email')} hint={t('You sign in with this. It is not verified by a code.', 'এটি দিয়ে সাইন ইন করবেন। কোড দিয়ে যাচাই হয় না।')}>{text('email', { type: 'email', autoComplete: 'email' })}</Field>
        <Field label={t('Mobile number', 'মোবাইল নম্বর')} required error={err('mobile')}>{text('mobile', { inputMode: 'tel', autoComplete: 'tel' })}</Field>
        {tab === 'company' && (
          <Field label={t('Department (optional)', 'বিভাগ (ঐচ্ছিক)')} required={false} error={err('department')}>{text('department')}</Field>
        )}
      </fieldset>
    </>
  )
  const passwords = (
    <fieldset className="m-0 flex flex-col gap-4 border-0 p-0">
      <legend className="mb-1 p-0 text-[13px] font-semibold tracking-[0.06em] text-muted-2 uppercase">{t('Password', 'পাসওয়ার্ড')}</legend>
      <Field label={t('Password', 'পাসওয়ার্ড')} required error={err('password')} hint={t('At least 12 characters with upper and lower case letters, a digit and a symbol.', 'কমপক্ষে ১২ অক্ষর: বড় ও ছোট হাতের অক্ষর, একটি সংখ্যা ও একটি চিহ্ন।')}>{text('password', { type: 'password', autoComplete: 'new-password' })}</Field>
      <Field label={t('Confirm password', 'পাসওয়ার্ড আবার লিখুন')} required error={err('confirm_password')}>{text('confirm_password', { type: 'password', autoComplete: 'new-password' })}</Field>
    </fieldset>
  )

  return (
    <AuthFrame
      wide
      title={t('Register with CredLens', 'CredLens-এ নিবন্ধন করুন')}
      lead={t('A new company registers its first Credit Officer. Colleagues join with the company’s invitation code.', 'নতুন প্রতিষ্ঠান প্রথম ক্রেডিট অফিসারকে নিবন্ধন করে। সহকর্মীরা কোম্পানির আমন্ত্রণ কোড দিয়ে যোগ দেন।')}
    >
      <div role="tablist" className="flex gap-2">
        {tabButton('company', t('New company', 'নতুন প্রতিষ্ঠান'), <Building2 size={17} aria-hidden="true" />)}
        {tabButton('join', t('Join with a code', 'কোড দিয়ে যোগ দিন'), <UserPlus size={17} aria-hidden="true" />)}
      </div>
      <form noValidate className="flex flex-col gap-6" onSubmit={(e) => void submit(e)}>
        {tab === 'join' && (
          <fieldset className="m-0 flex flex-col gap-4 border-0 p-0">
            <legend className="mb-1 p-0 text-[13px] font-semibold tracking-[0.06em] text-muted-2 uppercase">{t('Invitation', 'আমন্ত্রণ')}</legend>
            <Field label={t('Company invitation code', 'কোম্পানির আমন্ত্রণ কোড')} required error={err('invitation_code')}>{text('invitation_code', { autoComplete: 'off', placeholder: 'XXXX-XXXX-XXXX-XXXX' })}</Field>
            <Field label={t('I am joining as', 'আমি যোগ দিচ্ছি')} required error={err('role')}>
              <Select
                value={role}
                onChange={set('role')}
                placeholder={t('Choose your role', 'আপনার ভূমিকা বাছুন')}
                options={[
                  { value: 'records_officer', label: t('Records Desk officer', 'রেকর্ড ডেস্কের সদস্য') },
                  { value: 'credit_officer', label: t('Credit Officer', 'ক্রেডিট অফিসার') },
                ]}
              />
            </Field>
            {preview && (
              <Notice tone="success" title={t(`This code opens ${preview.organization_name}`, `এই কোড ${preview.organization_name} খোলে`)}>
                {t(`You will join as ${preview.role === 'records_officer' ? 'a Records Desk officer' : 'a Credit Officer'}. The code shows your link to the company; it is not a legal check of the company.`, `আপনি ${preview.role === 'records_officer' ? 'রেকর্ড ডেস্কের সদস্য' : 'ক্রেডিট অফিসার'} হিসেবে যোগ দেবেন। কোডটি শুধু কোম্পানির সাথে আপনার সম্পর্ক দেখায়; এটি কোম্পানির আইনি যাচাই নয়।`)}
              </Notice>
            )}
          </fieldset>
        )}
        {person}
        {tab === 'join' && role === 'records_officer' && (
          <fieldset className="m-0 flex flex-col gap-4 border-0 p-0">
            <legend className="mb-1 p-0 text-[13px] font-semibold tracking-[0.06em] text-muted-2 uppercase">{t('Employment', 'কর্মসংক্রান্ত')}</legend>
            <Field label={t('Employee or staff ID', 'কর্মী আইডি')} required error={err('employee_id')}>{text('employee_id')}</Field>
          </fieldset>
        )}
        {tab === 'company' && (
          <fieldset className="m-0 flex flex-col gap-4 border-0 p-0">
            <legend className="mb-1 p-0 text-[13px] font-semibold tracking-[0.06em] text-muted-2 uppercase">{t('Company', 'প্রতিষ্ঠান')}</legend>
            <Field label={t('Legal company name', 'কোম্পানির আইনি নাম')} required error={err('legal_name')}>{text('legal_name')}</Field>
            <Field label={t('Trading or brand name (optional)', 'ব্র্যান্ড নাম (ঐচ্ছিক)')} error={err('trading_name')}>{text('trading_name')}</Field>
            <Field label={t('Organisation type', 'প্রতিষ্ঠানের ধরন')} required error={err('org_type')}>
              <Select value={orgType} onChange={set('org_type')} placeholder={t('Choose one', 'একটি বাছুন')} options={ORG_TYPES.map(([value, en, bn]) => ({ value, label: t(en, bn) }))} />
            </Field>
            <Field
              label={NUMBER_REQUIRED.includes(orgType) ? t('Registration or licence number', 'নিবন্ধন বা লাইসেন্স নম্বর') : t('Registration number (if any)', 'নিবন্ধন নম্বর (থাকলে)')}
              required={NUMBER_REQUIRED.includes(orgType)}
              error={err('registration_number')}
            >
              {text('registration_number')}
            </Field>
            <Field label={t('Business sector', 'ব্যবসার খাত')} required error={err('sector')}>{text('sector')}</Field>
            <Field label={t('Official company email', 'কোম্পানির অফিসিয়াল ইমেইল')} required error={err('official_email')}>{text('official_email', { type: 'email' })}</Field>
            <Field label={t('Company contact number', 'কোম্পানির যোগাযোগ নম্বর')} required error={err('contact_number')}>{text('contact_number', { inputMode: 'tel' })}</Field>
            <Field label={t('Country (2 letters)', 'দেশ (২ অক্ষর)')} required error={err('country')}>{text('country', { maxLength: 2 })}</Field>
            <Field label={t('Division or state', 'বিভাগ বা রাজ্য')} required error={err('division')}>{text('division')}</Field>
            <Field label={t('City', 'শহর')} required error={err('city')}>{text('city')}</Field>
            <Field label={t('Full business address', 'পূর্ণ ব্যবসায়িক ঠিকানা')} required error={err('address')}>{text('address')}</Field>
            <Field label={t('Website (optional)', 'ওয়েবসাইট (ঐচ্ছিক)')} error={err('website')}>{text('website', { inputMode: 'url' })}</Field>
          </fieldset>
        )}
        {passwords}
        {general && (
          <p role="alert" className="m-0 rounded-[10px] border border-[#F3D0D0] bg-error-panel px-3 py-2 text-[14px] text-error">
            {general}
          </p>
        )}
        <Button type="submit" size="lg" disabled={pending}>
          {pending ? t('Registering…', 'নিবন্ধন হচ্ছে…') : tab === 'company' ? t('Register the company', 'প্রতিষ্ঠান নিবন্ধন করুন') : t('Join the company', 'কোম্পানিতে যোগ দিন')}
        </Button>
      </form>
      <p className="m-0 border-t border-line pt-4 text-[14px] text-body">
        {t('Already registered?', 'আগেই নিবন্ধন করেছেন?')}{' '}
        <Link to="/login" className="font-semibold no-underline">
          {t('Sign in', 'সাইন ইন')}
        </Link>
      </p>
    </AuthFrame>
  )
}
