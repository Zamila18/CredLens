/**
 * /dev/states (approved design: 11-interface-states-desktop.png): the interface states, drawn
 * by the same components the pages use, to compare with the design. Only while developing
 * (App.tsx adds the route in dev builds); not in the menu.
 *
 * The texts here are the components' own; there is no merchant data on this page.
 */
import { Database } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { useT } from '@/lib/i18n'

function Row({ n, label, children }: { n: number; label: string; children: ReactNode }) {
  return (
    <section className="grid gap-3 rounded-card border border-card-line bg-white p-4 md:grid-cols-[180px_minmax(0,1fr)]">
      <span className="self-start rounded-[8px] bg-mint px-3 py-1 text-sm font-semibold text-lens-dark">
        {n}. {label}
      </span>
      <div>{children}</div>
    </section>
  )
}

export function DevStates() {
  const t = useT()
  return (
    <Page>
      <PageHeader
        title={t('Interface states', 'ইন্টারফেসের অবস্থা')}
        description={t('How the interface explains loading, missing evidence and unavailable pages.', 'লোড হওয়া, প্রমাণের ঘাটতি আর না-পাওয়া পাতা ইন্টারফেস কীভাবে বোঝায়।')}
      />
      <Row n={1} label={t('Loading', 'লোড হচ্ছে')}>
        <LoadingState title={t('Loading the queue…', 'তালিকা আসছে…')} text={t('The queue is being fetched.', 'তালিকা আনা হচ্ছে।')} />
      </Row>
      <Row n={2} label={t('Empty results', 'ফলাফল নেই')}>
        <EmptyState title={t('No merchants match these filters.', 'এই ফিল্টারে কোনো মার্চেন্ট মেলেনি।')} text={t('The current filters returned no merchants.', 'এখনকার ফিল্টারে কোনো মার্চেন্ট আসেনি।')} />
      </Row>
      <Row n={3} label={t('Consent required', 'অনুমতি দরকার')}>
        <ErrorCallout error={{ status: 403, code: 'consent_required', message: '' }} />
      </Row>
      <Row n={4} label={t('Connection error', 'সংযোগে সমস্যা')}>
        <ErrorCallout error={{ status: 0, code: 'network', message: '' }} />
      </Row>
      <Row n={5} label={t('Unknown address', 'অজানা ঠিকানা')}>
        <ErrorCallout error={{ status: 404, code: 'not_found', message: '' }} />
      </Row>
      <Row n={6} label={t('Public-data mode', 'পাবলিক ডেটা মোড')}>
        <div className="mint-wash flex gap-4 rounded-card border border-mint-line p-5">
          <span className="flex size-14 shrink-0 items-center justify-center rounded-full bg-mint text-lens-dark" aria-hidden="true">
            <Database size={26} />
          </span>
          <div className="flex flex-col gap-2">
            <span className="text-sm text-body">{t('Public data: Taiwan credit cards, not ShopUp data. Decision support only.', 'পাবলিক ডেটা: তাইওয়ানের ক্রেডিট কার্ড, ShopUp-এর ডেটা নয়। শুধু সিদ্ধান্তে সহায়তা।')}</span>
            <span className="flex flex-wrap gap-2">
              <span className="rounded-md bg-mint px-2 py-0.5 text-[13px] font-semibold text-lens-dark">taiwan_cc · {t('Public', 'পাবলিক')}</span>
              <span className="rounded-md bg-ground px-2 py-0.5 font-mono text-[13px] text-ink-2">data_mode taiwan_cc</span>
            </span>
            <span className="font-display text-lg font-semibold text-ink">{t('No review queue for public data', 'পাবলিক ডেটায় পর্যালোচনার তালিকা নেই')}</span>
            <span className="text-[15px] text-body">
              {t(
                'In a public data mode every outcome is already known, so there are no merchants to review. This source shows its model card and totals only.',
                'পাবলিক ডেটায় প্রতিটি ফলাফল আগে থেকেই জানা, তাই পর্যালোচনার মতো কোনো মার্চেন্ট নেই। এই উৎস শুধু তার মডেল কার্ড ও মোট হিসাব দেখায়।',
              )}
            </span>
            <Link to="/model?mode=taiwan_cc" className="self-start rounded-[10px] bg-lens-dark px-4 py-2.5 text-[15px] font-semibold text-white no-underline hover:bg-lens-hover hover:text-white">
              {t('Open the model card', 'মডেল কার্ড খুলুন')}
            </Link>
          </div>
        </div>
      </Row>
    </Page>
  )
}
