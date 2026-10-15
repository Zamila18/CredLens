/** Stand-in for a page that a later part of Phase 10 builds. */
import { Card, Page, PageHeader } from '@/components/Page'

export function Placeholder({ title, part, mockup }: { title: string; part: string; mockup: string }) {
  return (
    <Page>
      <PageHeader title={title} />
      <Card className="p-5 text-sm text-ink-3">
        This page is built in {part}. It follows <span className="font-mono">{mockup}</span>.
      </Card>
    </Page>
  )
}

export function NotFound() {
  return (
    <Page>
      <PageHeader title="Page not found" description="There is no page at this address. Use the menu on the left." />
    </Page>
  )
}
