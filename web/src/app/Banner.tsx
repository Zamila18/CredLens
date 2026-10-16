/**
 * The banner strip on every page. Its English comes from GET /health (never written in
 * the app); in Bangla it is the matching sentence from src/lib/i18n.ts. The data source
 * in bold, then "Decision support only." Right side, mono: the data mode and the model
 * version (from GET /model/card).
 */
import type { Health, ModelCard } from '@/api/types'
import { useApi } from '@/api/useApi'
import { InfoIcon } from '@/components/icons'
import { BANNER_BN, useLang, useT } from '@/lib/i18n'

const DECISION_SUPPORT = 'Decision support only.'
const DECISION_SUPPORT_BN = 'শুধু সিদ্ধান্তে সহায়তা।'

/** "Synthetic demo data. Decision support only." -> ["Synthetic demo data.", "Decision support only."] */
function splitBanner(banner: string, promise: string, stop: string): [string, string] {
  const cut = banner.indexOf(stop)
  const first = cut === -1 ? banner : banner.slice(0, cut + 1)
  const rest = cut === -1 ? '' : banner.slice(cut + stop.length).trim()
  // The promise is that every screen says it; add it if the text ever leaves it out.
  return [first, banner.includes(promise) ? rest : `${rest} ${promise}`.trim()]
}

export function Banner() {
  const health = useApi<Health>('/health')
  const card = useApi<ModelCard>(health.data ? '/model/card' : null)
  const lang = useLang()
  const t = useT()

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-banner-line bg-banner px-4 py-2.5 text-[13px] sm:px-8">
      <div className="flex items-center gap-2.5 text-banner-text">
        <InfoIcon className="shrink-0" />
        {health.data ? (
          (() => {
            const [first, rest] =
              lang === 'bn'
                ? splitBanner(BANNER_BN[health.data.data_mode], DECISION_SUPPORT_BN, '। ')
                : splitBanner(health.data.banner, DECISION_SUPPORT, '. ')
            return (
              <span>
                <span className="font-semibold">{first}</span> <span>{rest}</span>
              </span>
            )
          })()
        ) : (
          <span>
            <span className="font-semibold">
              {health.error
                ? t('The API is not answering yet.', 'API এখনও সাড়া দিচ্ছে না।')
                : t('Connecting to the API…', 'API-র সাথে যুক্ত হচ্ছে…')}
            </span>{' '}
            <span>{t(DECISION_SUPPORT, DECISION_SUPPORT_BN)}</span>
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
