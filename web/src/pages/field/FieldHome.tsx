/**
 * Field work home: find a shop, add a new one, or continue with a recent one.
 *
 * Calls: GET /search/merchants (as the user types, from two letters), GET /field/shops
 * (shops created in the app, newest first, each with its next step). Both reads are
 * audited by the API. Nothing here is made up: no counts, no sample shops.
 */
import { ChevronRight, Store } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import type { MerchantSummary, WorkflowStatus } from '@/api/types'
import { useApi } from '@/api/useApi'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { SearchBox } from '@/components/Filters'
import { fmtDateTime } from '@/lib/format'
import { NEXT_STEP_WORDS, SHOP_TYPE_WORDS, wordsFor } from '@/lib/fieldWords'
import { pick, useLang, useT } from '@/lib/i18n'
import { DemoLine, FieldPage } from './shared'
import { useDemoSettings } from './fieldData'

function useDebounced(value: string, ms = 300) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(timer)
  }, [value, ms])
  return debounced
}

function ShopRow({ to, title, id, details, aside }: { to: string; title: string; id: string; details: string; aside?: string }) {
  return (
    <li>
      <Link
        to={to}
        className="flex min-h-14 items-center gap-3 border-t border-line px-1 py-3 text-ink no-underline hover:bg-row-hover hover:text-ink"
      >
        <Store size={20} strokeWidth={1.7} className="shrink-0 text-lens-dark" aria-hidden="true" />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-[15px] font-semibold">{title}</span>
          <span className="truncate text-[13px] text-muted-2">
            <span className="font-mono">{id}</span>
            {details && ` · ${details}`}
          </span>
        </span>
        {aside && <span className="hidden shrink-0 text-[13px] font-medium text-lens-dark sm:inline">{aside}</span>}
        <ChevronRight size={18} className="shrink-0 text-muted-2" aria-hidden="true" />
      </Link>
    </li>
  )
}

export function FieldHome() {
  const t = useT()
  const lang = useLang()
  const settings = useDemoSettings()
  const [query, setQuery] = useState('')
  const term = useDebounced(query.trim())
  const search = useApi<MerchantSummary[]>(term.length >= 2 ? '/search/merchants' : null, { q: term })
  const recent = useApi<WorkflowStatus[]>('/field/shops', { limit: 30 }, { noCache: true })

  const describe = (shop: MerchantSummary) =>
    [shop.area, shop.district, shop.shop_type ? wordsFor(SHOP_TYPE_WORDS, shop.shop_type, lang) : null].filter(Boolean).join(' · ')

  return (
    <FieldPage>
      <header className="flex flex-col gap-1">
        <h1 className="m-0 text-[28px] leading-9 font-bold tracking-[-0.02em]">{t('Field work', 'মাঠের কাজ')}</h1>
        <p className="m-0 text-[15px] text-body">
          {t('Find the shop you are visiting, or add it if it is new.', 'যে দোকানে যাচ্ছেন সেটি খুঁজুন, নতুন হলে যোগ করুন।')}
        </p>
      </header>
      <DemoLine settings={settings.data} />

      <section aria-labelledby="find-shop" className="flex flex-col gap-3">
        <h2 id="find-shop" className="m-0 text-lg font-semibold">
          {t('Find a shop', 'দোকান খুঁজুন')}
        </h2>
        <SearchBox value={query} onChange={setQuery} placeholder={t('Shop name, area or CredLens id', 'দোকানের নাম, এলাকা বা CredLens আইডি')} />
        {term.length >= 2 &&
          (search.error ? (
            <ErrorCallout error={search.error} />
          ) : search.loading ? (
            <p className="m-0 text-sm text-muted-2" role="status">
              {t('Searching…', 'খোঁজা হচ্ছে…')}
            </p>
          ) : search.data && search.data.length === 0 ? (
            <EmptyState
              title={t('No shop matches this search.', 'এই খোঁজে কোনো দোকান মেলেনি।')}
              text={t('Check the spelling, or add the shop as new.', 'বানান দেখুন, বা দোকানটি নতুন হিসেবে যোগ করুন।')}
            />
          ) : (
            <ul className="m-0 list-none p-0" aria-label={t('Search results', 'খোঁজের ফল')}>
              {search.data?.map((shop) => (
                <ShopRow
                  key={shop.merchant_id}
                  to={shop.created_in_app ? `/app/field/shops/${encodeURIComponent(shop.merchant_id)}` : `/app/merchants/${encodeURIComponent(shop.merchant_id)}`}
                  title={shop.shop_name ?? t('Benchmark merchant (read-only)', 'বেঞ্চমার্ক মার্চেন্ট (শুধু দেখা)')}
                  id={shop.merchant_id}
                  details={describe(shop)}
                />
              ))}
            </ul>
          ))}
      </section>


      <section aria-labelledby="recent-shops" className="flex flex-col gap-2">
        <h2 id="recent-shops" className="m-0 text-lg font-semibold">
          {t('Shops added in the app', 'অ্যাপে যোগ করা দোকান')}
        </h2>
        {recent.error ? (
          <ErrorCallout error={recent.error} />
        ) : recent.loading ? (
          <LoadingState title={t('Loading the shops…', 'দোকানগুলো আসছে…')} />
        ) : recent.data && recent.data.length === 0 ? (
          <EmptyState
            title={t('No shops added yet.', 'এখনও কোনো দোকান যোগ হয়নি।')}
            text={t('Add the first shop you visit.', 'প্রথম যে দোকানে যান সেটি যোগ করুন।')}
          />
        ) : (
          <ul className="m-0 list-none p-0">
            {recent.data?.map((status) => (
              <ShopRow
                key={status.merchant.merchant_id}
                to={`/app/field/shops/${encodeURIComponent(status.merchant.merchant_id)}`}
                title={status.merchant.shop_name ?? status.merchant.merchant_id}
                id={status.merchant.merchant_id}
                details={[describe(status.merchant), status.created_at ? fmtDateTime(status.created_at) : null].filter(Boolean).join(' · ')}
                aside={pick(NEXT_STEP_WORDS[status.next_step], lang)}
              />
            ))}
          </ul>
        )}
      </section>
    </FieldPage>
  )
}
