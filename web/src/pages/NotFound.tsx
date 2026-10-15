/** Shown for an address that has no page. */
import { Page, PageHeader } from '@/components/Page'

export function NotFound() {
  return (
    <Page>
      <PageHeader title="Page not found" description="There is no page at this address. Use the menu on the left." />
    </Page>
  )
}
