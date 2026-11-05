/**
 * Merchants: every merchant, searched and paged on the server (GET /directory/merchants),
 * so the browser never loads thousands of rows. Shops added in the app come first.
 * A shop added in the app opens its Field Mode page for officers (where its records are
 * kept); every merchant also has its review page.
 */
import { Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import type { DirectoryPage as Directory, DirectoryRow } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSession } from '@/app/session-context'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { FilterSegments, Pager, SearchBox } from '@/components/Filters'
import { Page, PageHeader } from '@/components/Page'
import { StatusTag } from '@/components/StatusTag'
import { Button } from '@/components/ui/button'
import { count, fmtDate } from '@/lib/format'
import { SHOP_TYPE_WORDS, wordsFor } from '@/lib/fieldWords'
import { useLang, useT } from '@/lib/i18n'
import type { StatusWords } from '@/lib/statuses'

type Source = 'all' | 'app' | 'benchmark'
const PAGE_SIZE = 25

function consentWords(c: DirectoryRow["consent"]): StatusWords {
  if (c === 'valid') return { en: 'Consent valid', bn: 'অনুমতি বৈধ', tone: 'strong', help: { en: 'A valid consent is on record.', bn: 'বৈধ অনুমতি রেকর্ডে আছে।' } }
  if (c === 'refused') return { en: 'Consent refused', bn: 'অনুমতি দেননি', tone: 'amber', help: { en: 'The merchant did not agree. Nothing can be recorded.', bn: 'মার্চেন্ট রাজি হননি। কিছু রাখা যাবে না।' } }
  return { en: 'No consent', bn: 'অনুমতি নেই', tone: 'neutral', help: { en: 'No valid consent is on record.', bn: 'কোনো বৈধ অনুমতি রেকর্ডে নেই।' } }
}

function link(row: DirectoryRow): string {
  return `/app/merchants/${encodeURIComponent(row.merchant_id)}`
}

export function DirectoryPage() {
  const t = useT()
  const lang = useLang()
  const { role, mode } = useSession()
  const [typed, setTyped] = useState('')
  const [q, setQ] = useState('')
  const [source, setSource] = useState<Source>('all')
  const [page, setPage] = useState(1)

  // Ask the server a moment after typing stops, not on every key.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQ(typed.trim())
      setPage(1)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [typed])

  const data = useApi<Directory>('/directory/merchants', { q, source, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE })
  const pages = data.data ? Math.max(1, Math.ceil(data.data.total / PAGE_SIZE)) : 1

  return (
    <Page>
      <PageHeader
        title={t('Merchants', 'মার্চেন্ট')}
        description={
          t('Your organisation’s shops. Search by name, area, district or CredLens id.', 'আপনার প্রতিষ্ঠানের দোকান। নাম, এলাকা, জেলা বা CredLens আইডি দিয়ে খুঁজুন।')
        }
        aside={
          role === 'credit_officer' ? (
            <Link to="/app/registrations/new" className="no-underline">
              <Button>
                <Plus size={17} aria-hidden="true" />
                {t('Register a merchant', 'মার্চেন্ট নিবন্ধন করুন')}
              </Button>
            </Link>
          ) : undefined
        }
      />

      <div className="flex flex-col gap-4 rounded-card border border-card-line bg-card p-4 md:flex-row md:items-end md:justify-between">
        <SearchBox value={typed} onChange={setTyped} placeholder={t('Search merchants', 'মার্চেন্ট খুঁজুন')} className="md:w-[380px]" />
        {mode !== 'account' && (
        <FilterSegments<Source>
          label={t('Source', 'উৎস')}
          value={source}
          onChange={(v) => {
            setSource(v)
            setPage(1)
          }}
          options={[
            { value: 'all', label: t('All', 'সব') },
          ]}
        />
        )}
      </div>

      {data.error ? (
        <ErrorCallout error={data.error} />
      ) : !data.data ? (
        <LoadingState title={t('Loading merchants…', 'মার্চেন্ট আসছে…')} />
      ) : data.data.items.length === 0 ? (
        <EmptyState title={t('No merchant matches', 'কোনো মার্চেন্ট মেলেনি')} text={t('Check the spelling, or search by CredLens id.', 'বানান দেখুন, বা CredLens আইডি দিয়ে খুঁজুন।')} />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="m-0 text-sm text-body">{t(`${count(data.data.total)} merchants`, `${count(data.data.total)} মার্চেন্ট`)}</p>
            <Pager page={page} pages={pages} onPage={setPage} />
          </div>
          <div className="hidden overflow-hidden rounded-card border border-card-line bg-card md:block">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-ground text-[12.5px] text-muted-2">
                <tr>
                  <th className="px-4 py-2.5 font-medium">{t('Merchant', 'মার্চেন্ট')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('Location', 'এলাকা')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('Shop type', 'দোকানের ধরন')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('Consent', 'অনুমতি')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('Application', 'আবেদন')}</th>
                </tr>
              </thead>
              <tbody>
                {data.data.items.map((row) => (
                  <tr key={row.merchant_id} className="border-t border-line hover:bg-row-hover">
                    <td className="px-4 py-3">
                      <Link to={link(row)} className="font-semibold no-underline">
                        {row.shop_name ?? row.merchant_id}
                      </Link>
                      <div className="text-[12.5px] text-muted-2">
                        <span className="font-mono">{row.merchant_id}</span> ·{' '}
                        {t(`added ${fmtDate(row.onboarded_at)}`, `যোগ হয়েছে ${fmtDate(row.onboarded_at)}`)}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-ink-2">{[row.area, row.district].filter(Boolean).join(', ') || '—'}</td>
                    <td className="px-4 py-3 text-ink-2">{row.shop_type ? wordsFor(SHOP_TYPE_WORDS, row.shop_type, lang) : '—'}</td>
                    <td className="px-4 py-3">
                      <StatusTag status={consentWords(row.consent)} />
                    </td>
                    <td className="px-4 py-3 text-ink-2">{row.has_application ? t('Application on file', 'আবেদন আছে') : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="m-0 flex list-none flex-col gap-2.5 p-0 md:hidden">
            {data.data.items.map((row) => (
              <li key={row.merchant_id}>
                <Link to={link(row)} className="flex flex-col gap-1.5 rounded-card border border-card-line bg-card p-4 no-underline">
                  <span className="text-[16px] font-semibold text-ink">{row.shop_name ?? row.merchant_id}</span>
                  <span className="text-[13px] text-muted-2">
                    <span className="font-mono">{row.merchant_id}</span>
                    {[row.area, row.district].filter(Boolean).length > 0 && ` · ${[row.area, row.district].filter(Boolean).join(', ')}`}
                  </span>
                  <span className="flex flex-wrap items-center gap-2">
                    <StatusTag status={consentWords(row.consent)} />
                    {row.has_application && <span className="text-[13px] text-ink-2">{t('Application on file', 'আবেদন আছে')}</span>}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <div className="flex justify-end">
            <Pager page={page} pages={pages} onPage={setPage} />
          </div>
        </>
      )}
    </Page>
  )
}
