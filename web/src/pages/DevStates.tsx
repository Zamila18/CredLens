/**
 * /dev/states: the React version of States.dc.html, to compare the shared components
 * with the design side by side. Not in the menu.
 *
 * The numbers here are design samples to show each state, not data. Every real
 * screen takes its numbers from the API.
 */
import type { ReactNode } from 'react'

import { ApiError } from '@/api/client'
import { ERROR_STATUS, KNOWN_ERROR_CODES } from '@/api/errors'
import type { Reason } from '@/api/types'
import { ActionCard } from '@/components/ActionCard'
import { BandChip } from '@/components/BandChip'
import { CoverageBar } from '@/components/CoverageBar'
import { ErrorCallout } from '@/components/ErrorCallout'
import { LensMark } from '@/components/icons'
import { LensDial } from '@/components/LensDial'
import { Card } from '@/components/Page'
import { ReasonCard } from '@/components/ReasonCard'
import { StatTile } from '@/components/StatTile'

const SWATCHES: [string, string, string][] = [
  ['Ink', '#13201C', 'text'],
  ['Night', '#0F1D19', 'sidebar'],
  ['Ground', '#F4F5F1', 'page'],
  ['Lens green', '#0E5A4A', 'Strong, primary'],
  ['Marigold', '#E0A44A', 'focus mark only'],
  ['Amber', '#B5650D', 'Review, holds back'],
  ['Periwinkle', '#8A97BF', 'Needs more info'],
  ['Slate blue', '#4A5A8C', 'deliveries, habits'],
  ['Rust', '#8A3A10', 'low-score warning'],
  ['Coverage', '#2D4F45', 'outer ring'],
]

// Sample reasons, copied from the mockup, to show both card colours and both languages.
const SAMPLE_HOLDS: Reason = {
  code: 'sample',
  sentence_en: 'Returns are higher than similar shops; this may reflect delivery conditions.',
  sentence_bn: 'সমান ধরনের দোকানের তুলনায় ফেরত বেশি; এটা ডেলিভারির পরিস্থিতির কারণেও হতে পারে।',
  contribution: -1.5,
  detail: 'Returns 7.5% vs average 4.0%',
}
const SAMPLE_HELPS: Reason = {
  code: 'sample',
  sentence_en: 'Stock purchases are growing compared with the previous three months.',
  sentence_bn: 'আগের তিন মাসের তুলনায় মাল কেনা বাড়ছে।',
  contribution: 3.0,
  detail: null,
}

function H2({ children }: { children: ReactNode }) {
  return <h2 className="m-0 text-[13px] font-semibold tracking-[.08em] text-muted uppercase">{children}</h2>
}

function LensCase({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <Card className="flex flex-col items-center gap-3 px-2.5 py-5">
      {children}
      <span className="px-2.5 text-center text-[13px] text-ink-3">{caption}</span>
    </Card>
  )
}

export function DevStates() {
  return (
    <div className="box-border flex w-full max-w-[1200px] flex-col gap-11 px-4 py-10 sm:px-14">
      <header className="flex items-end justify-between gap-6">
        <div className="flex flex-col gap-2">
          <h1 className="m-0 text-[44px] leading-[48px] font-semibold tracking-[-0.02em]">CredLens system</h1>
          <p className="m-0 max-w-[640px] text-base text-ink-3">
            One idea runs through every screen: a score is never alone. It sits inside a coverage ring, wears its
            band, and shows its reasons.
          </p>
          <p className="m-0 font-mono text-xs text-muted-2">/dev/states · reference board · sample values, not data</p>
        </div>
        <LensMark size={72} outer="#0E5A4A" ring="#13201C" />
      </header>

      <section className="flex flex-col gap-4">
        <H2>Colour</H2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          {SWATCHES.map(([name, hex, use]) => (
            <div key={name} className="flex flex-col gap-2">
              <i className="block h-16 rounded-panel shadow-[inset_0_0_0_1px_#D5D9D0]" style={{ background: hex }} />
              <b className="text-[13px] font-semibold">{name}</b>
              <span className="font-mono text-xs text-muted">
                {hex} · {use}
              </span>
            </div>
          ))}
        </div>
        <p className="m-0 text-sm text-ink-3">
          No red anywhere. A thin file is uncertain, not bad, so Needs more info is a cool periwinkle with a dashed
          edge, never an alarm colour. Bands differ in lightness as well as hue.
        </p>
      </section>

      <section className="flex flex-col gap-4">
        <H2>Type</H2>
        <div className="grid gap-4 md:grid-cols-3">
          <Card className="flex flex-col gap-2 p-5">
            <span className="text-[34px] font-semibold tracking-[-0.01em]">Aa Review queue</span>
            <span className="font-mono text-xs text-muted">IBM Plex Sans · UI and copy</span>
          </Card>
          <Card className="flex flex-col gap-2 p-5">
            <span className="font-mono text-[34px] font-semibold tracking-[-0.02em]">94 · ৳1,48,000</span>
            <span className="font-mono text-xs text-muted">IBM Plex Mono · scores, ids, money</span>
          </Card>
          <Card className="flex flex-col gap-2 p-5">
            <span className="font-bn text-[30px] font-medium">মাল কেনা বাড়ছে</span>
            <span className="font-mono text-xs text-muted">Noto Sans Bengali · Bangla reasons</span>
          </Card>
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <H2>The lens: four states</H2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <LensCase caption="Strong. Proceed with normal checks.">
            <LensDial score={94} coverage={0.85} band="Strong" lowScoreWarning={false} />
          </LensCase>
          <LensCase caption="Below 70: read every reason.">
            <LensDial score={48} coverage={0.75} band="Review" lowScoreWarning />
          </LensCase>
          <LensCase caption="Coverage under 45%: the number is greyed, the ask is evidence.">
            <LensDial score={66} coverage={0.35} band="Needs more info" lowScoreWarning />
          </LensCase>
          <LensCase caption="Consent revoked: no score, no decision.">
            <LensDial noConsent />
          </LensCase>
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <H2>Queue pieces</H2>
        <Card className="flex flex-wrap items-center gap-6 p-5">
          <BandChip band="Strong" />
          <BandChip band="Review" lowScoreWarning />
          <BandChip band="Needs more info" />
          <BandChip band={null} noneLabel="No consent" />
          <CoverageBar coverage={0.85} band="Strong" />
          <CoverageBar coverage={0.35} band="Needs more info" />
        </Card>
        <div className="grid gap-3 sm:grid-cols-3">
          <StatTile label="Pending" value="—" />
          <StatTile label="Needs more info" value="—" valueClassName="text-peri-text" />
          <StatTile label="Officer agreed with the band" value="—" caption="accepts against overrides" />
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        <div className="flex flex-col gap-4">
          <H2>Decision actions</H2>
          <div role="radiogroup" aria-label="Action (sample)" className="grid grid-cols-2 gap-2.5">
            <ActionCard label="Accept suggestion" hint="Selected state" selected />
            <ActionCard label="Override: raise" hint="Reason required" selected={false} />
            <ActionCard label="Override: lower" hint="Reason required" selected={false} />
            <ActionCard label="Needs more info" hint="Note optional" selected={false} />
          </div>
          <p className="m-0 text-sm text-ink-3">
            There is no Approve or Decline button anywhere, and the API refuses those words. Record decision stays
            disabled until an override has a written reason.
          </p>
        </div>
        <div className="flex flex-col gap-4">
          <H2>Reason card</H2>
          <ReasonCard reason={SAMPLE_HOLDS} lang="en" maxAbs={3} />
          <ReasonCard reason={SAMPLE_HELPS} lang="bn" maxAbs={3} />
          <p className="m-0 text-sm text-ink-3">
            Officers read sentences, never feature codes. Delivery reasons stay neutral observations.
          </p>
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <H2>When the API says no</H2>
        <div className="grid gap-4 md:grid-cols-2">
          {KNOWN_ERROR_CODES.map((code) => (
            <ErrorCallout
              key={code}
              error={new ApiError(ERROR_STATUS[code] ?? 500, code, '(the API’s own message appears here)')}
            />
          ))}
        </div>
      </section>
    </div>
  )
}
