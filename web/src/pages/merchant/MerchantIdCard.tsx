/**
 * The shop's Merchant ID, for its handover slip (GET /merchants/{id}/access; every view is
 * recorded). The merchant signs in at /login (Merchant card) with this ID and the owner's name.
 * "Print the slip" opens a plain page to print and give to the owner; "Give a new ID" makes a
 * new random ID and ends the old one.
 */
import { Copy, KeyRound, Printer } from 'lucide-react'
import { useState } from 'react'

import { api } from '@/api/client'
import type { MerchantAccessOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Section } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { useT } from '@/lib/i18n'

const esc = (value: string) => value.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string)

export function MerchantIdCard({ merchantId, className }: { merchantId: string; className?: string }) {
  const t = useT()
  const path = `/merchants/${encodeURIComponent(merchantId)}/access`
  const access = useApi<MerchantAccessOut>(path, undefined, { noCache: true })
  const reissue = useSubmit<MerchantAccessOut>()
  const [copied, setCopied] = useState(false)
  const a = access.data

  const copy = async () => {
    if (!a) return
    try {
      await navigator.clipboard.writeText(a.portal_id)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  const print = () => {
    if (!a) return
    const w = window.open('', '_blank', 'width=720,height=900')
    if (!w) return
    const site = window.location.origin
    w.document.write(`<!doctype html><meta charset="utf-8"><title>Merchant ID</title>
<style>body{font-family:system-ui,sans-serif;margin:48px;color:#0b1533}h1{font-size:28px;margin:0 0 4px}
.id{font:700 40px/1.2 ui-monospace,monospace;letter-spacing:.06em;border:2px dashed #0b1533;border-radius:12px;padding:18px 24px;display:inline-block;margin:22px 0}
li{margin:8px 0;font-size:18px}p{font-size:16px;color:#46506b}</style>
<h1>${esc(a.shop_name ?? '')}</h1><p>${esc(a.owner_name ?? '')}</p>
<div class="id">${esc(a.portal_id)}</div>
<ol><li>Open <b>${esc(site)}/login</b></li><li>Choose <b>I am a merchant</b></li>
<li>Type this Merchant ID and the owner’s name</li></ol>
<p>Keep this slip safe. Anyone who has it and knows the owner’s name can see this shop’s records.</p>
<p>এই মার্চেন্ট আইডি ও মালিকের নাম দিয়ে ${esc(site)}/login পাতায় “আমি একজন ব্যবসায়ী” বেছে সাইন ইন করুন।</p>
<script>window.onload=()=>window.print()</script>`)
    w.document.close()
  }

  return (
    <Section className={className} title={t('Merchant ID', 'মার্চেন্ট আইডি')} answer={t('The shop owner signs in to their own page with this ID and their name.', 'দোকান মালিক এই আইডি ও নাম দিয়ে নিজের পাতায় সাইন ইন করেন।')}>
      {access.error ? (
        <ErrorCallout error={access.error} />
      ) : !a ? null : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-[12px] border-2 border-dashed border-ink px-4 py-2.5 font-mono text-[26px] font-bold tracking-[0.06em] text-ink">{a.portal_id}</span>
            <Button variant="outline" onClick={() => void copy()}>
              <Copy size={18} aria-hidden="true" />
              {copied ? t('Copied', 'কপি হয়েছে') : t('Copy', 'কপি')}
            </Button>
            <Button variant="outline" onClick={print}>
              <Printer size={18} aria-hidden="true" />
              {t('Print the slip', 'স্লিপ ছাপুন')}
            </Button>
          </div>
          <p className={`m-0 text-[14.5px] ${a.portal_open ? 'text-body' : 'font-semibold text-amber-text'}`}>{a.portal_open ? t('The merchant signs in with this ID and the owner’s name.', 'ব্যবসায়ী এই আইডি ও মালিকের নাম দিয়ে সাইন ইন করেন।') : t('The page opens once the consent form has been checked.', 'সম্মতিপত্র যাচাই হলে পাতাটি খুলবে।')}</p>
          {reissue.error && <ErrorCallout error={reissue.error} />}
          <div>
            <Button
              variant="ghost"
              disabled={reissue.pending}
              onClick={() => {
                if (window.confirm(t('Give this shop a new Merchant ID? The old one stops working.', 'এই দোকানকে নতুন মার্চেন্ট আইডি দেবেন? পুরোনোটি আর কাজ করবে না।'))) {
                  void reissue.submit(() => api<MerchantAccessOut>(`${path}/reissue`, { method: 'POST' })).then(() => access.reload())
                }
              }}
            >
              <KeyRound size={18} aria-hidden="true" />
              {t('Give a new ID', 'নতুন আইডি দিন')}
            </Button>
          </div>
        </div>
      )}
    </Section>
  )
}
