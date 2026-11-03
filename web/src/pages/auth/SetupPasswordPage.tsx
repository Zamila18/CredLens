/**
 * Set or reset one's password with the one-time code an administrator gave (POST
 * /auth/password/setup). The administrator never sees the password. Every earlier session of
 * the account ends; the person then signs in with the new password.
 */
import { KeyRound } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { api, ApiError } from '@/api/client'
import { Field, TextInput } from '@/components/form'
import { Notice } from '@/components/Notice'
import { Button } from '@/components/ui/button'
import { useT } from '@/lib/i18n'
import { AuthFrame } from './AuthFrame'

const MIN = 10

export function SetupPasswordPage() {
  const t = useT()
  const [identifier, setIdentifier] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const [touched, setTouched] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [done, setDone] = useState(false)

  const problems = {
    identifier: identifier.trim() ? null : t('Enter your email or mobile number.', 'আপনার ইমেইল বা মোবাইল নম্বর লিখুন।'),
    code: code.trim().length >= 6 ? null : t('Enter the code from your administrator.', 'অ্যাডমিনের দেওয়া কোড লিখুন।'),
    password: password.length >= MIN ? null : t(`Use at least ${MIN} characters.`, `অন্তত ${MIN}টি অক্ষর ব্যবহার করুন।`),
    repeat: repeat === password ? null : t('The two passwords are not the same.', 'দুটি পাসওয়ার্ড এক নয়।'),
  }

  const submit = async () => {
    setTouched(true)
    if (Object.values(problems).some(Boolean)) return
    setPending(true)
    setError(null)
    try {
      await api('/auth/password/setup', { method: 'POST', json: { identifier: identifier.trim(), code: code.trim(), password } })
      setDone(true)
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'network', 'The API could not be reached.'))
    } finally {
      setPending(false)
    }
  }

  if (done) {
    return (
      <AuthFrame title={t('Your password is set', 'আপনার পাসওয়ার্ড ঠিক হয়েছে')} lead={t('Sign in with it now.', 'এখন এটি দিয়ে সাইন ইন করুন।')}>
        <Link to="/login" className="inline-flex min-h-12 items-center justify-center rounded-[10px] bg-lens-dark px-5 font-semibold text-white no-underline hover:text-white">
          {t('Go to sign in', 'সাইন ইনে যান')}
        </Link>
      </AuthFrame>
    )
  }

  return (
    <AuthFrame
      title={t('Set your password', 'আপনার পাসওয়ার্ড ঠিক করুন')}
      lead={t('Your administrator gives you a one-time code when your account is made or reset. Only you choose the password.', 'অ্যাকাউন্ট তৈরি বা রিসেট হলে অ্যাডমিন একবারের একটি কোড দেন। পাসওয়ার্ড শুধু আপনিই বাছেন।')}
    >
      <form noValidate className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); void submit() }}>
        <Field label={t('Email or mobile number', 'ইমেইল বা মোবাইল নম্বর')} required error={touched ? problems.identifier : null}>
          <TextInput value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="username" />
        </Field>
        <Field label={t('One-time code', 'একবারের কোড')} required hint="XXXX-XXXX-XXXX" error={touched ? problems.code : null}>
          <TextInput value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} autoComplete="one-time-code" spellCheck={false} />
        </Field>
        <Field label={t('New password', 'নতুন পাসওয়ার্ড')} required hint={t(`At least ${MIN} characters. A short sentence is easy to remember.`, `অন্তত ${MIN}টি অক্ষর। ছোট একটি বাক্য মনে রাখা সহজ।`)} error={touched ? problems.password : null}>
          <TextInput type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
        </Field>
        <Field label={t('New password again', 'আবার নতুন পাসওয়ার্ড')} required error={touched ? problems.repeat : null}>
          <TextInput type="password" value={repeat} onChange={(e) => setRepeat(e.target.value)} autoComplete="new-password" />
        </Field>
        {error && (
          <Notice tone="error" title={error.code === 'bad_code' ? t('This code does not work', 'এই কোড কাজ করছে না') : t('The password was not set', 'পাসওয়ার্ড ঠিক হয়নি')}>
            {error.code === 'bad_code'
              ? t('It may be used, expired or typed differently. Ask your administrator for a new one.', 'এটি ব্যবহৃত, মেয়াদোত্তীর্ণ বা ভুল লেখা হতে পারে। অ্যাডমিনের কাছে নতুন কোড চান।')
              : error.message}
          </Notice>
        )}
        <Button type="submit" size="lg" disabled={pending}>
          <KeyRound size={18} aria-hidden="true" />
          {pending ? t('Saving…', 'রাখা হচ্ছে…') : t('Set password', 'পাসওয়ার্ড ঠিক করুন')}
        </Button>
      </form>
      <Link to="/login" className="text-[14px] no-underline">
        {t('Back to sign in', 'সাইন ইনে ফিরে যান')}
      </Link>
    </AuthFrame>
  )
}
