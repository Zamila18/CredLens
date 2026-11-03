/**
 * Sign in to CredLens with one's own account: email or mobile number, and password
 * (POST /auth/login). The server decides the role and the organisation; the browser keeps
 * only an HttpOnly session cookie. After signing in, each role lands on its own start page.
 * New company: /register. Forgot the password: the owner's one-time code at /setup-password.
 */
import { LogIn } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router'

import { ApiError } from '@/api/client'
import { HOME } from '@/app/navigation'
import { useSession } from '@/app/session-context'
import { Field, TextInput } from '@/components/form'
import { Notice } from '@/components/Notice'
import { Button } from '@/components/ui/button'
import { useT } from '@/lib/i18n'
import { AuthFrame } from './AuthFrame'

export function LoginPage() {
  const t = useT()
  const [params] = useSearchParams()
  const { mode, role, signIn } = useSession()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const next = params.get('next')
  const justRegistered = params.get('registered') === '1'

  // Signed in (also right after submitting): go where the person was heading, or home.
  if (mode === 'account') return <Navigate to={next && next.startsWith('/app') ? next : HOME[role]} replace />

  const submit = async () => {
    setPending(true)
    setError(null)
    try {
      await signIn(identifier.trim(), password)
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'network', 'The API could not be reached.'))
    } finally {
      setPending(false)
    }
  }

  const message = !error
    ? null
    : error.code === 'login_failed'
      ? t('The email/number or password is not right.', 'ইমেইল/নম্বর বা পাসওয়ার্ড ঠিক নয়।')
      : error.code === 'account_locked'
        ? t('Too many wrong attempts. Wait 15 minutes and try again, or ask your administrator.', 'অনেকবার ভুল হয়েছে। ১৫ মিনিট পর আবার চেষ্টা করুন, বা অ্যাডমিনকে বলুন।')
        : error.code === 'no_active_membership'
          ? t('This account has no active access. Ask your administrator.', 'এই অ্যাকাউন্টের সক্রিয় প্রবেশাধিকার নেই। অ্যাডমিনকে বলুন।')
          : error.code === 'validation'
            ? t('Enter your email or mobile number and your password.', 'আপনার ইমেইল বা মোবাইল নম্বর ও পাসওয়ার্ড লিখুন।')
            : t('Signing in did not work. Check your connection and try again.', 'সাইন ইন হয়নি। সংযোগ দেখে আবার চেষ্টা করুন।')

  return (
    <AuthFrame
      title={t('Sign in to CredLens', 'CredLens-এ সাইন ইন করুন')}
      lead={t('Use the email or mobile number your organisation registered for you.', 'আপনার প্রতিষ্ঠান যে ইমেইল বা মোবাইল নম্বর দিয়েছে তা ব্যবহার করুন।')}
    >
      {justRegistered && (
        <Notice tone="success" title={t('Registration complete', 'নিবন্ধন সম্পন্ন')}>
          {t('Your account is ready. Sign in with your email or mobile number and your password.', 'আপনার অ্যাকাউন্ট তৈরি হয়েছে। ইমেইল বা মোবাইল নম্বর ও পাসওয়ার্ড দিয়ে সাইন ইন করুন।')}
        </Notice>
      )}
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        <Field label={t('Email or mobile number', 'ইমেইল বা মোবাইল নম্বর')} required>
          <TextInput value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="username" inputMode="email" autoFocus />
        </Field>
        <Field label={t('Password', 'পাসওয়ার্ড')} required>
          <TextInput type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        </Field>
        {message && (
          <p role="alert" className="m-0 rounded-[10px] border border-[#F3D0D0] bg-error-panel px-3 py-2 text-[14px] text-error">
            {message}
          </p>
        )}
        <Button type="submit" size="lg" disabled={pending || !identifier.trim() || !password}>
          <LogIn size={18} aria-hidden="true" />
          {pending ? t('Signing in…', 'সাইন ইন হচ্ছে…') : t('Sign in', 'সাইন ইন')}
        </Button>
      </form>
      <div className="flex flex-col gap-2 border-t border-line pt-4 text-[14px] text-body">
        <span>
          {t('New to CredLens?', 'CredLens-এ নতুন?')}{' '}
          <Link to="/register" className="font-semibold no-underline">
            {t('Register your company or join with an invitation code', 'আপনার প্রতিষ্ঠান নিবন্ধন করুন বা আমন্ত্রণ কোড দিয়ে যোগ দিন')}
          </Link>
        </span>
        <span className="text-[13px] text-muted-2">
          {t('Forgot your password?', 'পাসওয়ার্ড ভুলে গেছেন?')}{' '}
          <Link to="/setup-password" className="no-underline">
            {t('Use the one-time code from your company owner', 'কোম্পানির মালিকের দেওয়া একবারের কোড ব্যবহার করুন')}
          </Link>
        </span>
      </div>
    </AuthFrame>
  )
}
