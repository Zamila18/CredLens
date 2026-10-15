/**
 * The banner strip on every page. Its text comes from GET /health (never written in
 * the app): the data source in bold, then "Decision support only." Right side, mono:
 * the data mode and the model version (from GET /model/card).
 */
import type { Health, ModelCard } from '@/api/types'
import { useApi } from '@/api/useApi'
import { InfoIcon } from '@/components/icons'

const DECISION_SUPPORT = 'Decision support only.'

/** "Synthetic demo data. Decision support only." -> ["Synthetic demo data.", "Decision support only."] */
function splitBanner(banner: string): [string, string] {
  const cut = banner.indexOf('. ')
  const first = cut === -1 ? banner : banner.slice(0, cut + 1)
  const rest = cut === -1 ? '' : banner.slice(cut + 2)
  // The promise is that every screen says it; add it if the API text ever leaves it out.
  return [first, banner.includes(DECISION_SUPPORT) ? rest : `${rest} ${DECISION_SUPPORT}`.trim()]
}

export function Banner() {
  const health = useApi<Health>('/health')
  const card = useApi<ModelCard>(health.data ? '/model/card' : null)

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-banner-line bg-banner px-4 py-2.5 text-[13px] sm:px-8">
      <div className="flex items-center gap-2.5 text-banner-text">
        <InfoIcon className="shrink-0" />
        {health.data ? (
          (() => {
            const [first, rest] = splitBanner(health.data.banner)
            return (
              <span>
                <span className="font-semibold">{first}</span> <span>{rest}</span>
              </span>
            )
          })()
        ) : (
          <span>
            <span className="font-semibold">{health.error ? 'The API is not answering yet.' : 'Connecting to the API…'}</span>{' '}
            <span>{DECISION_SUPPORT}</span>
          </span>
        )}
      </div>
      {health.data && (
        <div className="font-mono text-xs text-muted-2">
          data_mode {health.data.data_mode}
          {card.data && ` · model ${card.data.model_version}`}
        </div>
      )}
    </div>
  )
}
