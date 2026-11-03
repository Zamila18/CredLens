/**
 * Merchant registrations: every registration case of the company, and the two ways to start
 * one: type the details (a prefilled consent form follows), or give out a blank form that the
 * merchant fills in by hand and bring it back here as a photo or scan.
 */
import { FilePlus2, FileUp, Printer } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { api } from '@/api/client'
import type { RegistrationOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Notice } from '@/components/Notice'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtDate } from '@/lib/format'
import { useT } from '@/lib/i18n'
import { saveBlob } from './registrationWords'
import { StatusChip } from './StatusChip'

export function RegistrationsPage() {
  const t = useT()
  const navigate = useNavigate()
  const list = useApi<RegistrationOut[]>('/registrations', undefined, { noCache: true })
  const file = useRef<HTMLInputElement>(null)
  const upload = useSubmit<RegistrationOut>()
  const [blankError, setBlankError] = useState<string | null>(null)

  const sendFilled = async (chosen: File | undefined) => {
    if (!chosen) return
    const made = await upload.submit(() =>
      api<RegistrationOut>('/registrations/from-form', {
        method: 'POST',
        query: { name: chosen.name },
        body: { content: chosen, contentType: chosen.type || 'application/octet-stream' },
      }),
    )
    if (made) navigate(`/app/registrations/${made.reg_id}`)
  }

  return (
    <Page>
      <PageHeader
        title={t('Merchant registrations', 'মার্চেন্ট নিবন্ধন')}
        description={t(
          'A merchant is registered with a printed consent form that the merchant signs. A person checks the signed copy before the merchant can be assessed.',
          'মার্চেন্ট নিবন্ধন হয় প্রিন্ট করা সম্মতিপত্রে, যাতে মার্চেন্ট সই করেন। মূল্যায়নের আগে একজন মানুষ সই করা কপি যাচাই করেন।',
        )}
      />
      <div className="grid gap-3 md:grid-cols-2">
        <section className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-5">
          <h2 className="m-0 text-[17px] font-semibold">{t('1. Type the details, print the form', '১. তথ্য টাইপ করুন, ফর্ম প্রিন্ট করুন')}</h2>
          <p className="m-0 text-[14px] text-body">{t('Enter the merchant’s details. The consent form comes out with them filled in and a reference number.', 'মার্চেন্টের তথ্য দিন। সম্মতিপত্র সেগুলো ভরা অবস্থায় ও একটি রেফারেন্স নম্বরসহ আসবে।')}</p>
          <Link to="/app/registrations/new" className="no-underline">
            <Button>
              <FilePlus2 size={17} aria-hidden="true" />
              {t('Register a merchant', 'মার্চেন্ট নিবন্ধন করুন')}
            </Button>
          </Link>
        </section>
        <section className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-5">
          <h2 className="m-0 text-[17px] font-semibold">{t('2. A blank form filled in by hand', '২. হাতে ভরা ফাঁকা ফর্ম')}</h2>
          <p className="m-0 text-[14px] text-body">{t('Download a blank form for the merchant to fill in and sign, then upload the photo or scan. The text is read for you to check.', 'মার্চেন্টের ভরে সই করার জন্য একটি ফাঁকা ফর্ম নামান, তারপর ছবি বা স্ক্যান আপলোড করুন। লেখা পড়ে আপনার যাচাইয়ের জন্য দেওয়া হবে।')}</p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() => saveBlob('/registration-forms/blank', 'credlens-blank-form.pdf').catch((e) => setBlankError(String(e.message ?? e)))}
            >
              <Printer size={17} aria-hidden="true" />
              {t('Download a blank form', 'ফাঁকা ফর্ম নামান')}
            </Button>
            <Button variant="outline" disabled={upload.pending} onClick={() => file.current?.click()}>
              <FileUp size={17} aria-hidden="true" />
              {upload.pending ? t('Uploading…', 'আপলোড হচ্ছে…') : t('Upload a filled form', 'ভরা ফর্ম আপলোড করুন')}
            </Button>
            <input ref={file} type="file" hidden accept="image/jpeg,image/png,application/pdf" capture="environment" onChange={(e) => void sendFilled(e.target.files?.[0])} />
          </div>
          {blankError && <p className="m-0 text-[13px] text-error">{blankError}</p>}
          {upload.error && <ErrorCallout error={upload.error} />}
        </section>
      </div>
      <Notice tone="info" title={t('Before real use', 'আসল ব্যবহারের আগে')}>
        {t(
          'The consent wording is a draft prepared for review by Bangladesh counsel. It is stamped DRAFT until a platform administrator approves it after that review.',
          'সম্মতির ভাষা বাংলাদেশের আইনজীবীর পর্যালোচনার জন্য তৈরি খসড়া। সেই পর্যালোচনার পর প্ল্যাটফর্ম অ্যাডমিন অনুমোদন না দেওয়া পর্যন্ত এতে খসড়া ছাপ থাকে।',
        )}
      </Notice>
      <section className="flex flex-col gap-3">
        <h2 className="m-0 text-[18px] font-semibold">{t('Cases', 'কেস')}</h2>
        {list.error ? (
          <ErrorCallout error={list.error} />
        ) : !list.data ? (
          <LoadingState title={t('Loading…', 'আসছে…')} />
        ) : list.data.length === 0 ? (
          <EmptyState title={t('No registration yet', 'এখনও কোনো নিবন্ধন নেই')} text={t('Register the first merchant with one of the two ways above.', 'ওপরের দুটির একটি উপায়ে প্রথম মার্চেন্ট নিবন্ধন করুন।')} />
        ) : (
          <ul className="m-0 flex list-none flex-col overflow-hidden rounded-card border border-card-line bg-card p-0">
            {list.data.map((r) => (
              <li key={r.reg_id} className="border-t border-line first:border-t-0">
                <Link to={`/app/registrations/${r.reg_id}`} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 no-underline hover:bg-row-hover">
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate text-[15px] font-semibold text-ink">{r.shop_name ?? t('(details to be read from the form)', '(ফর্ম থেকে তথ্য পড়া হবে)')}</span>
                    <span className="text-[13px] text-muted-2">
                      {r.reg_ref} · {r.method === 'manual' ? t('typed details', 'টাইপ করা তথ্য') : t('blank form', 'ফাঁকা ফর্ম')} · {fmtDate(r.created_at)}
                    </span>
                  </span>
                  <StatusChip status={r.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </Page>
  )
}
