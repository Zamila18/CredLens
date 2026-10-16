/** Shown for an address that has no page. */
import { Page, PageHeader } from '@/components/Page'
import { useT } from '@/lib/i18n'

export function NotFound() {
  const t = useT()
  return (
    <Page>
      <PageHeader
        title={t('Page not found', 'পাতা পাওয়া যায়নি')}
        description={t('There is no page at this address. Use the menu on the left.', 'এই ঠিকানায় কোনো পাতা নেই। বাঁ দিকের মেনু ব্যবহার করুন।')}
      />
    </Page>
  )
}
