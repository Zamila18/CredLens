/** Shown for an address that has no page (approved design: states sheet, "Unknown address"). */
import { ErrorCallout } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { useT } from '@/lib/i18n'

export function NotFound() {
  const t = useT()
  return (
    <Page>
      <PageHeader title={t('Page not found', 'পাতা পাওয়া যায়নি')} />
      <ErrorCallout error={{ status: 404, code: 'not_found', message: '' }} className="max-w-[720px]" />
    </Page>
  )
}
