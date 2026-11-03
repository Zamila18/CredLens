/**
 * Register a merchant, method 1: type the details. The merchant row is made at once, without
 * consent; the next screen prints the consent form with these details filled in.
 *
 * Only what the assessment needs is asked. There is no field for a national ID or an account
 * number, by design. Fields marked * are required.
 */
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'

import { ApiError, api } from '@/api/client'
import type { DemoSettings, RegistrationOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { Field, Select, TextInput } from '@/components/form'
import { Notice } from '@/components/Notice'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { SHOP_TYPE_WORDS, wordsFor } from '@/lib/fieldWords'
import { pick, useLang, useT } from '@/lib/i18n'
import { DETAILS, OWNERSHIP } from './registrationWords'

export function NewRegistrationPage() {
  const t = useT()
  const lang = useLang()
  const navigate = useNavigate()
  const settings = useApi<DemoSettings>('/demo/settings')
  const [v, setV] = useState<Record<string, string>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [duplicates, setDuplicates] = useState<{ merchant_id: string; shop_name: string; area: string | null }[] | null>(null)
  const [pending, setPending] = useState(false)
  const [general, setGeneral] = useState<string | null>(null)

  const set = (key: string) => (e: { target: { value: string } }) => setV((old) => ({ ...old, [key]: e.target.value }))

  const submit = async (e: FormEvent, confirmNew = false) => {
    e.preventDefault()
    setPending(true)
    setErrors({})
    setGeneral(null)
    try {
      const made = await api<RegistrationOut>('/registrations', { method: 'POST', json: { ...v, confirm_new: confirmNew } })
      navigate(`/app/registrations/${made.reg_id}`)
    } catch (err) {
      if (err instanceof ApiError) {
        const facts = err.facts as { fields?: Record<string, string>; candidates?: typeof duplicates }
        if (facts.fields) setErrors(facts.fields)
        if (err.code === 'possible_duplicate' && facts.candidates) setDuplicates(facts.candidates)
        else setGeneral(err.message)
      } else setGeneral(t('The API could not be reached.', 'API-তে পৌঁছানো যায়নি।'))
    } finally {
      setPending(false)
    }
  }

  const control = (key: string) => {
    if (key === 'district')
      return <Select value={v.district ?? ''} onChange={set('district')} placeholder={t('Choose a district', 'জেলা বাছুন')} options={(settings.data?.districts ?? []).map((d) => ({ value: d, label: d }))} />
    if (key === 'shop_type')
      return <Select value={v.shop_type ?? ''} onChange={set('shop_type')} placeholder={t('Choose one', 'একটি বাছুন')} options={(settings.data?.shop_types ?? []).map((s) => ({ value: s, label: wordsFor(SHOP_TYPE_WORDS, s, lang) }))} />
    if (key === 'ownership_type')
      return <Select value={v.ownership_type ?? ''} onChange={set('ownership_type')} placeholder={t('Choose one', 'একটি বাছুন')} options={Object.entries(OWNERSHIP).map(([value, pair]) => ({ value, label: pick({ en: pair[0], bn: pair[1] }, lang) }))} />
    const numeric = ['established_year', 'branches'].includes(key)
    const phone = key.includes('mobile') || key === 'alternate_contact'
    return <TextInput value={v[key] ?? ''} onChange={set(key)} inputMode={numeric ? 'numeric' : phone ? 'tel' : undefined} />
  }

  return (
    <Page>
      <PageHeader
        title={t('Register a merchant', 'মার্চেন্ট নিবন্ধন')}
        description={t('Type the merchant’s details. A consent form with these details comes next, to print and have signed.', 'মার্চেন্টের তথ্য টাইপ করুন। এরপর এই তথ্যসহ একটি সম্মতিপত্র পাবেন, প্রিন্ট করে সই করানোর জন্য।')}
      />
      <Notice tone="info" title={t('We ask only what the assessment needs', 'আমরা শুধু মূল্যায়নের জন্য যা দরকার তা-ই চাই')}>
        {t('No national ID number and no bank or mobile-money account number. Fields marked * are required.', 'জাতীয় পরিচয়পত্র নম্বর বা ব্যাংক/মোবাইল-মানি অ্যাকাউন্ট নম্বর নেই। * চিহ্নিত ঘর আবশ্যক।')}
      </Notice>
      <form noValidate className="grid gap-4 rounded-card border border-card-line bg-card p-5 md:grid-cols-2" onSubmit={(e) => void submit(e)}>
        {DETAILS.map(([key, en, bn, required]) => (
          <Field key={key} label={t(en, bn)} required={required} error={errors[key] ?? null}>
            {control(key)}
          </Field>
        ))}
        {duplicates && (
          <div className="md:col-span-2">
            <Notice tone="warning" title={t('A shop with this name may already exist', 'এই নামের একটি দোকান আগেই থাকতে পারে')}>
              <ul className="m-0 pl-5">
                {duplicates.map((d) => (
                  <li key={d.merchant_id}>
                    {d.shop_name} {d.area ? `· ${d.area}` : ''} ({d.merchant_id})
                  </li>
                ))}
              </ul>
              <Button type="button" variant="outline" className="mt-2" disabled={pending} onClick={(e) => void submit(e as unknown as FormEvent, true)}>
                {t('This is a different shop: register it', 'এটি আলাদা দোকান: নিবন্ধন করুন')}
              </Button>
            </Notice>
          </div>
        )}
        {general && (
          <p role="alert" className="m-0 rounded-[10px] border border-[#F3D0D0] bg-error-panel px-3 py-2 text-[14px] text-error md:col-span-2">
            {general}
          </p>
        )}
        <div className="md:col-span-2">
          <Button type="submit" size="lg" disabled={pending}>
            {pending ? t('Saving…', 'সংরক্ষণ হচ্ছে…') : t('Save and continue to the consent form', 'সংরক্ষণ করে সম্মতিপত্রে যান')}
          </Button>
        </div>
      </form>
    </Page>
  )
}
