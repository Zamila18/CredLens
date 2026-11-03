/**
 * Data sources: the organisation's connections and the catalogue of every kind of source
 * (GET /sources, GET /sources/catalog). Built-in sources work without a connection and
 * link to their own screens; a planned source says plainly that it is not connected.
 * Only administrators add connections, and only for sources that can be connected now.
 */
import { ArrowRight, Plus, Plug } from 'lucide-react'
import { Link } from 'react-router'

import type { ConnectorInfo, SourceConnectionOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSession } from '@/app/session-context'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { StatusTag } from '@/components/StatusTag'
import { count, fmtBdTime } from '@/lib/format'
import { pick, useLang, useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { AVAILABILITY, BUILTIN_LINK, CATEGORY, CONNECTION_STATUS } from './words'

const ORDER = ['manual', 'file', 'institutional', 'test', 'platform', 'financial', 'logistics', 'pos', 'distributor', 'accounting']

function Connections({ rows }: { rows: SourceConnectionOut[] }) {
  const t = useT()
  if (!rows.length) {
    return (
      <div className="flex flex-col items-start gap-2 rounded-card border border-dashed border-control-line bg-card p-6">
        <Plug size={22} aria-hidden="true" className="text-muted-2" />
        <span className="text-[16px] font-semibold text-ink">{t('No connections yet', 'এখনও কোনো সংযোগ নেই')}</span>
        <span className="text-[14px] text-body">
          {t('Field entry and spreadsheet imports work without one. Connections bring in records from other systems.', 'মাঠের এন্ট্রি ও স্প্রেডশিট আমদানি সংযোগ ছাড়াই কাজ করে। সংযোগ অন্য সিস্টেম থেকে রেকর্ড আনে।')}
        </span>
      </div>
    )
  }
  return (
    <ul className="m-0 flex list-none flex-col overflow-hidden rounded-card border border-card-line bg-card p-0">
      {rows.map((c) => (
        <li key={c.connection_id} className="border-t border-line first:border-t-0">
          <Link to={`/app/sources/${encodeURIComponent(c.connection_id)}`} className="grid gap-2 px-4 py-3.5 no-underline hover:bg-row-hover sm:grid-cols-[minmax(0,1.3fr)_auto_minmax(0,1.2fr)_auto] sm:items-center">
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-[15px] font-semibold text-ink">{c.display_name}</span>
              <span className="text-[13px] text-muted-2">{c.connector_name}</span>
            </span>
            <StatusTag status={CONNECTION_STATUS[c.status]} />
            <span className="text-[13px] text-body">
              {c.last_run
                ? c.last_run.status === 'ok'
                  ? t(
                      `Last ${c.last_run.kind} ${fmtBdTime(c.last_run.finished_at)}${c.last_run.kind === 'sync' ? ` · ${count(c.last_run.rows_added)} saved` : ''}`,
                      `শেষ ${c.last_run.kind} ${fmtBdTime(c.last_run.finished_at)}${c.last_run.kind === 'sync' ? ` · ${count(c.last_run.rows_added)}টি রাখা` : ''}`,
                    )
                  : t(`Last ${c.last_run.kind} failed ${fmtBdTime(c.last_run.finished_at)}`, `শেষ ${c.last_run.kind} ব্যর্থ ${fmtBdTime(c.last_run.finished_at)}`)
                : t('Never run', 'কখনো চালানো হয়নি')}
            </span>
            <ArrowRight size={16} aria-hidden="true" className="hidden text-muted-2 sm:block" />
          </Link>
        </li>
      ))}
    </ul>
  )
}

export function SourcesPage() {
  const t = useT()
  const lang = useLang()
  const { role } = useSession()
  const catalog = useApi<ConnectorInfo[]>('/sources/catalog')
  const sources = useApi<SourceConnectionOut[]>('/sources', undefined, { noCache: true })

  const groups = ORDER.map((cat) => ({ cat, items: (catalog.data ?? []).filter((c) => c.category === cat) })).filter((g) => g.items.length)

  return (
    <Page>
      <PageHeader
        title={t('Data sources', 'ডেটার উৎস')}
        description={t(
          'Where this organisation’s evidence comes from. Every saved record keeps its source, and nothing is linked to a merchant without a person confirming it.',
          'এই প্রতিষ্ঠানের প্রমাণ কোথা থেকে আসে। প্রতিটি রাখা রেকর্ডে তার উৎস থাকে, আর মানুষ নিশ্চিত না করলে কিছুই মার্চেন্টের সাথে যুক্ত হয় না।',
        )}
        aside={
          role === 'credit_officer' ? (
            <Link to="/app/sources/new" className="lift inline-flex min-h-11 items-center gap-2 rounded-[10px] bg-lens-dark px-4 font-semibold text-white no-underline hover:text-white">
              <Plus size={17} aria-hidden="true" />
              {t('Add a connection', 'সংযোগ যোগ করুন')}
            </Link>
          ) : undefined
        }
      />

      <section className="flex flex-col gap-3">
        <h2 className="m-0 text-[18px] font-semibold">{t('Connections', 'সংযোগ')}</h2>
        {sources.error ? <ErrorCallout error={sources.error} /> : !sources.data ? <LoadingState title={t('Loading connections…', 'সংযোগ আসছে…')} /> : <Connections rows={sources.data} />}
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="m-0 text-[18px] font-semibold">{t('Source catalogue', 'উৎসের তালিকা')}</h2>
        {catalog.error ? (
          <ErrorCallout error={catalog.error} />
        ) : !catalog.data ? (
          <LoadingState title={t('Loading the catalogue…', 'তালিকা আসছে…')} />
        ) : (
          <div className="grid gap-5 lg:grid-cols-2">
            {groups.map((g) => (
              <div key={g.cat} className="flex flex-col gap-2">
                <span className="text-[12px] font-semibold tracking-[0.07em] text-muted-2 uppercase">{pick(CATEGORY[g.cat] ?? { en: g.cat, bn: g.cat }, lang)}</span>
                {g.items.map((c) => {
                  const link = BUILTIN_LINK[c.key]
                  const canUse = link && (!link.roles || link.roles.includes(role))
                  return (
                    <div key={c.key} className={cn('flex flex-col gap-2 rounded-panel border bg-card p-4', c.availability === 'planned' ? 'border-line' : 'border-card-line')}>
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <span className="flex flex-col">
                          <span className={cn('text-[15px] font-semibold', c.availability === 'planned' ? 'text-ink-2' : 'text-ink')}>{lang === 'bn' ? c.name_bn : c.name}</span>
                          {c.example && <span className="text-[12.5px] text-muted-2">{c.example}{t(' (example only, no partnership)', ' (শুধু উদাহরণ, কোনো অংশীদারিত্ব নয়)')}</span>}
                        </span>
                        <StatusTag status={AVAILABILITY[c.availability]} />
                      </div>
                      <span className="text-[14px] leading-[21px] text-body">{lang === 'bn' ? c.description_bn : c.description}</span>
                      {c.availability === 'builtin' && canUse && (
                        <Link to={link.to} className="inline-flex items-center gap-1 self-start text-[14px] font-semibold no-underline">
                          {t(link.en, link.bn)}
                          <ArrowRight size={14} aria-hidden="true" />
                        </Link>
                      )}
                      {c.availability === 'available' && role === 'credit_officer' && (
                        <Link to={`/app/sources/new?connector=${encodeURIComponent(c.key)}`} className="inline-flex items-center gap-1 self-start text-[14px] font-semibold no-underline">
                          {t('Set up a connection', 'সংযোগ তৈরি করুন')}
                          <ArrowRight size={14} aria-hidden="true" />
                        </Link>
                      )}
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
        )}
      </section>
    </Page>
  )
}
