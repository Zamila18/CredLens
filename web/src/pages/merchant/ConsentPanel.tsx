/**
 * Consent panel (not drawn in the mockup; DESIGN_SPEC section 6 item 1): the merchant's
 * consent as GET /merchants/{id}/consent reads it live from the database.
 * There is no revoke button on purpose: the scorer reads consent once at start-up,
 * so a revoke would not stop scoring until the API restarts.
 */
import type { ConsentView } from '@/api/types'
import { Chip } from '@/components/BandChip'
import { CheckIcon } from '@/components/icons'
import { Card } from '@/components/Page'
import { categoriesOf, humanize } from '@/lib/consent'
import { fmtDate } from '@/lib/format'

export function CategoryChip({ children }: { children: string }) {
  return <span className="inline-flex rounded-md border border-card-line bg-[#F1F3EE] px-2 py-0.5 text-xs text-ink-2">{children}</span>
}

export function ConsentPanel({ consent }: { consent: ConsentView }) {
  return (
    <Card className="flex flex-col gap-3.5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="m-0 text-lg font-semibold">Consent</h2>
        {consent.valid ? (
          <Chip tone="strong" className="px-2.5 py-1">
            <CheckIcon /> Valid
          </Chip>
        ) : (
          <Chip className="px-2.5 py-1 shadow-[inset_0_0_0_1.5px_#9AA39E]">No valid consent</Chip>
        )}
      </div>
      <p className="m-0 text-[13px] text-muted">
        Checked for <span className="font-mono tabular">{fmtDate(consent.as_of)}</span>, the last day in the data.
      </p>
      {consent.data_categories.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-semibold">Data allowed</span>
          <div className="flex flex-wrap gap-1.5">
            {consent.data_categories.map((c) => (
              <CategoryChip key={c}>{c}</CategoryChip>
            ))}
          </div>
        </div>
      ) : (
        <p className="m-0 text-sm text-ink-3">No data may be used for this merchant.</p>
      )}
      {consent.records.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[460px] border-collapse text-[13px]">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th scope="col" className="py-1.5 font-semibold">Record</th>
                <th scope="col" className="py-1.5 font-semibold">Purpose</th>
                <th scope="col" className="py-1.5 font-semibold">Granted</th>
                <th scope="col" className="py-1.5 font-semibold">Expires</th>
                <th scope="col" className="py-1.5 font-semibold">Revoked</th>
              </tr>
            </thead>
            <tbody>
              {consent.records.map((r, i) => (
                <tr key={r.consent_id ?? i} className="border-t border-line-soft align-top">
                  <td className="py-2 pr-2 font-mono">{r.consent_id ?? '—'}</td>
                  <td className="py-2 pr-2">
                    <div>{humanize(r.purpose)}</div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {categoriesOf(r.data_categories).map((c) => (
                        <CategoryChip key={c}>{c}</CategoryChip>
                      ))}
                    </div>
                  </td>
                  <td className="py-2 pr-2 font-mono tabular">{fmtDate(r.granted_at)}</td>
                  <td className="py-2 pr-2 font-mono tabular">{fmtDate(r.expires_at)}</td>
                  <td className="py-2 font-mono tabular">{fmtDate(r.revoked_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="m-0 text-sm text-ink-3">No consent records exist for this merchant.</p>
      )}
      <p className="m-0 text-xs text-muted-2">
        Read live from the database; this read is audited. There is no revoke button here on purpose.
      </p>
    </Card>
  )
}
