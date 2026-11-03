/**
 * A short note on a merchant's page when the shop has data-quality issues: how many need
 * attention and how many problems a person confirmed (records are kept, never removed).
 * Shows nothing when there are none. Links to the Data quality page for this shop.
 */
import { Link } from 'react-router'

import type { QualityReport } from '@/api/types'
import { useApi } from '@/api/useApi'
import { Notice } from '@/components/Notice'
import { count } from '@/lib/format'
import { useT } from '@/lib/i18n'

export function MerchantQualityNote({ merchantId, className }: { merchantId: string; className?: string }) {
  const t = useT()
  const report = useApi<QualityReport>('/quality/issues', { status: 'all', merchant_id: merchantId }, { noCache: true })
  const issues = report.data?.issues ?? []
  const open = issues.filter((i) => i.status !== 'reviewed').length
  const concerns = issues.filter((i) => i.status === 'reviewed' && i.reviews[0]?.concern).length
  if (!open && !concerns) return null
  return (
    <Notice
      tone="warning"
      className={className}
      title={t('Data quality', 'ডেটার মান')}
      action={
        <Link to={`/app/quality?merchant=${encodeURIComponent(merchantId)}`} className="text-[14px] font-semibold no-underline">
          {t('See the issues', 'সমস্যাগুলো দেখুন')}
        </Link>
      }
    >
      {[
        open ? t(`${count(open)} need attention.`, `${count(open)}টি মনোযোগ চায়।`) : '',
        concerns ? t(`${count(concerns)} confirmed by a reviewer; the records are kept as they are.`, `${count(concerns)}টি পর্যালোচক নিশ্চিত করেছেন; রেকর্ড যেমন আছে থাকে।`) : '',
      ].filter(Boolean).join(' ')}
    </Notice>
  )
}
