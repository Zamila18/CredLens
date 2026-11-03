/** Plain words for the data-quality screen: groups, statuses, issue kinds and outcomes. */
import type { QualityIssueOut } from '@/api/types'
import { count, fmtBdTime, fmtDate, taka } from '@/lib/format'
import type { Lang, Pair } from '@/lib/i18n'
import type { StatusWords } from '@/lib/statuses'

export const GROUPS: Record<string, Pair> = {
  identity: { en: 'Shop identity', bn: 'দোকানের পরিচয়' },
  duplicates: { en: 'Duplicates', bn: 'দ্বৈত রেকর্ড' },
  sources: { en: 'Sources and imports', bn: 'উৎস ও আমদানি' },
  completeness: { en: 'Missing or old evidence', bn: 'অনুপস্থিত বা পুরনো প্রমাণ' },
  consent: { en: 'Consent', bn: 'অনুমতি' },
}

export const ISSUE_STATUS: Record<string, StatusWords> = {
  open: { en: 'Needs attention', bn: 'মনোযোগ দরকার', tone: 'amber', help: { en: 'Nobody has reviewed this yet.', bn: 'এখনও কেউ পর্যালোচনা করেননি।' } },
  changed: { en: 'Changed since review', bn: 'পর্যালোচনার পরে বদলেছে', tone: 'amber', help: { en: 'The records changed after the last review, so it needs another look.', bn: 'শেষ পর্যালোচনার পরে রেকর্ড বদলেছে, তাই আবার দেখা দরকার।' } },
  reviewed: { en: 'Reviewed', bn: 'পর্যালোচিত', tone: 'strong', help: { en: 'A person recorded what they found.', bn: 'একজন যা পেয়েছেন তা লিখেছেন।' } },
  concern: { en: 'Problem confirmed', bn: 'সমস্যা নিশ্চিত', tone: 'peri', help: { en: 'Reviewed and confirmed. The records stay as they are and the merchant’s review shows it.', bn: 'পর্যালোচিত ও নিশ্চিত। রেকর্ড যেমন আছে থাকে আর মার্চেন্টের পর্যালোচনায় দেখায়।' } },
}

export const OUTCOMES: Record<string, Pair & { detail: Pair }> = {
  different_shops: { en: 'They are different shops', bn: 'এগুলো আলাদা দোকান', detail: { en: 'Both stay as they are.', bn: 'দুটোই যেমন আছে থাকে।' } },
  same_shop: { en: 'They are the same shop', bn: 'এগুলো একই দোকান', detail: { en: 'Nothing is merged; both reviews show a warning.', bn: 'কিছু একত্র হয় না; দুটো পর্যালোচনায় সতর্কতা দেখায়।' } },
  records_correct: { en: 'The records belong to this shop', bn: 'রেকর্ডগুলো এই দোকানের', detail: { en: 'They stay as evidence.', bn: 'সেগুলো প্রমাণ হিসেবে থাকে।' } },
  records_wrong: { en: 'They are not this shop’s records', bn: 'এগুলো এই দোকানের রেকর্ড নয়', detail: { en: 'Kept, and flagged on the merchant’s review.', bn: 'রাখা থাকে, মার্চেন্টের পর্যালোচনায় চিহ্নিত।' } },
  both_genuine: { en: 'Each is a real purchase', bn: 'প্রতিটি আসল কেনাকাটা', detail: { en: 'For example two memos on one day.', bn: 'যেমন একই দিনে দুটি মেমো।' } },
  duplicate: { en: 'The same purchase was recorded twice', bn: 'একই কেনাকাটা দুবার লেখা', detail: { en: 'Kept, and flagged on the merchant’s review.', bn: 'রাখা থাকে, মার্চেন্টের পর্যালোচনায় চিহ্নিত।' } },
  leave_as_is: { en: 'Leave these rows out', bn: 'এই সারিগুলো বাদ থাকুক', detail: { en: 'Until the next sync changes the picture.', bn: 'পরের সিঙ্কে অবস্থা না বদলানো পর্যন্ত।' } },
  acknowledged: { en: 'Checked; nothing more to add', bn: 'দেখা হয়েছে; আর কিছু যোগের নেই', detail: { en: 'For example the rows were wrong in the file.', bn: 'যেমন ফাইলেই সারিগুলো ভুল ছিল।' } },
}

export const ORIGIN: Record<string, Pair> = {
  staff_entered: { en: 'Typed in by staff', bn: 'কর্মী লিখেছেন' },
  imported_spreadsheet: { en: 'Spreadsheet import', bn: 'স্প্রেডশিট আমদানি' },
  data_source: { en: 'Data source', bn: 'ডেটার উৎস' },
  synthetic_demo: { en: 'Synthetic demo', bn: 'সিনথেটিক ডেমো' },
  admin_import: { en: 'Data file', bn: 'ডেটা ফাইল' },
}

const MISSING: Record<string, Pair> = {
  purchases: { en: 'purchase', bn: 'কেনাকাটার' },
  deliveries: { en: 'delivery', bn: 'ডেলিভারির' },
}

type F = Record<string, unknown>
const s = (v: unknown) => (v == null ? '' : String(v))
const n = (v: unknown) => count(Number(v ?? 0))
/** "2 refused and 1 possible duplicate": only the parts that are not zero. */
function parts(items: [unknown, string, string][], bn: boolean): string {
  const kept = items.filter(([v]) => Number(v ?? 0) > 0).map(([v, one, many]) => (bn ? `${n(v)}টি ${one}` : `${n(v)} ${Number(v) === 1 ? one : many}`))
  if (kept.length < 2) return kept.join('')
  return `${kept.slice(0, -1).join(', ')}${bn ? ' ও ' : ' and '}${kept[kept.length - 1]}`
}

/** The issue's title and one-paragraph explanation, from its kind and facts. */
export function describe(issue: QualityIssueOut, lang: Lang): { title: string; text: string } {
  const f = issue.facts as F
  const bn = lang === 'bn'
  switch (issue.kind) {
    case 'possible_same_shop':
      return bn
        ? { title: 'দুটি দোকান একই হতে পারে', text: `${s(f.shop_name)} (${issue.merchant_id}) ও ${s(f.other_shop_name)} (${issue.other_merchant_id}) — ${s(f.district)} জেলায় একই নাম। নাম মিল মানে একই দোকান নয়; CredLens নিজে কখনো দোকান একত্র করে না।` }
        : { title: 'Two shops may be the same', text: `${s(f.shop_name)} (${issue.merchant_id}) and ${s(f.other_shop_name)} (${issue.other_merchant_id}) have the same name in ${s(f.district)}. A matching name does not make them the same shop, and CredLens never merges shops by itself.` }
    case 'withdrawn_link':
      return bn
        ? { title: 'তুলে নেওয়া মিলের রেকর্ড', text: `মিল তুলে নেওয়ার আগে ${s(f.connection_name)} থেকে ${s(f.shop_name) || issue.merchant_id}-এর জন্য ${n(f.records)}টি রেকর্ড রাখা হয়েছিল। সেগুলো মোছা হয়নি। এগুলো এই দোকানের কি না জানান।` }
        : { title: 'Records from a withdrawn match', text: `${n(f.records)} ${Number(f.records) === 1 ? 'record was' : 'records were'} saved from ${s(f.connection_name)} for ${s(f.shop_name) || issue.merchant_id} before the match was withdrawn. They have not been deleted. Say whether they belong to this shop.` }
    case 'possible_duplicate_record':
      return bn
        ? { title: 'সম্ভাব্য দ্বৈত কেনাকাটা', text: `${fmtDate(s(f.business_date))} তারিখে ${taka(Number(f.amount))}-এর ${n(f.records)}টি কেনাকাটা${Number(f.sources) > 1 ? `, ${n(f.sources)}টি উৎস থেকে` : ''}। একই দিনে দুটি আসল মেমো হতে পারে, আবার একই কেনাকাটা দুবারও লেখা হতে পারে।` }
        : { title: 'Possible duplicate purchase', text: `${n(f.records)} purchases of ${taka(Number(f.amount))} on ${fmtDate(s(f.business_date))}${Number(f.sources) > 1 ? `, from ${n(f.sources)} different sources` : ''}. Two real memos on one day are possible; so is one purchase recorded twice.` }
    case 'source_rows_left_out':
      return bn
        ? { title: 'সিঙ্কে বাদ পড়া সারি', text: `${s(f.connection_name)}-এর শেষ সিঙ্ক (${fmtBdTime(s(f.at))}) বাদ রেখেছে: ${parts([[f.unmatched, 'মেলানোর অপেক্ষায়', ''], [f.rejected, 'বাতিল', ''], [f.flagged, 'সম্ভাব্য দ্বৈত', '']], true)}। বাদ পড়া সারি রাখা হয়নি।` }
        : { title: 'Rows a sync left out', text: `The last sync of ${s(f.connection_name)} (${fmtBdTime(s(f.at))}) left out ${parts([[f.unmatched, 'row waiting for a merchant match', 'rows waiting for a merchant match'], [f.rejected, 'refused row', 'refused rows'], [f.flagged, 'possible duplicate', 'possible duplicates']], false)}. None of them were saved.` }
    case 'source_failing':
      return bn
        ? { title: 'একটি ডেটার উৎস ব্যর্থ হচ্ছে', text: `${s(f.connection_name)}-এর শেষ চালানো ব্যর্থ (${fmtBdTime(s(f.at))})। তা থেকে কিছু রাখা হয়নি। কারণ ঠিক করে আবার পরীক্ষা করুন।` }
        : { title: 'A data source is failing', text: `The last run of ${s(f.connection_name)} failed (${fmtBdTime(s(f.at))}). Nothing from it was saved. Fix the cause and test it again.` }
    case 'import_rows_left_out':
      return bn
        ? { title: 'স্প্রেডশিটের বাদ পড়া সারি', text: `${s(f.file_name)}${f.sheet_name ? ` (${s(f.sheet_name)})` : ''}${f.shop_name ? `, ${s(f.shop_name)}` : ''}: ${n(f.added)}টি রাখা; ${parts([[f.rejected, 'বাতিল', ''], [f.flagged, 'সম্ভাব্য দ্বৈত', '']], true)} বাদ পড়েছে।` }
        : { title: 'Spreadsheet rows left out', text: `${s(f.file_name)}${f.sheet_name ? ` (${s(f.sheet_name)})` : ''}${f.shop_name ? ` for ${s(f.shop_name)}` : ''}: ${n(f.added)} saved; ${parts([[f.rejected, 'refused row', 'refused rows'], [f.flagged, 'possible duplicate', 'possible duplicates']], false)} left out.` }
    case 'missing_evidence': {
      const kinds = ((f.missing as string[]) ?? []).map((k) => (bn ? MISSING[k]?.bn : MISSING[k]?.en) ?? k)
      return bn
        ? { title: 'আবেদনের প্রমাণ নেই', text: `${s(f.shop_name)}-এর খোলা আবেদন আছে, কিন্তু কোনো ${kinds.join(' বা ')} রেকর্ড নেই। রেকর্ড না থাকা একটি ফাঁক, দোকানের বিরুদ্ধে কারণ নয়।` }
        : { title: 'Evidence missing for an application', text: `${s(f.shop_name)} has an open application but no ${kinds.join(' or ')} records. Missing records are a gap to fill, never a reason against the shop.` }
    }
    case 'stale_evidence':
      return bn
        ? { title: 'প্রমাণ পুরনো হয়ে যাচ্ছে', text: `${s(f.shop_name)}-এর সর্বশেষ কেনাকাটা ${fmtDate(s(f.newest))}, ব্যবসার ক্যালেন্ডার শেষের ${n(f.days)} দিন আগে (সীমা ${n(f.limit_days)} দিন)। নতুন রেকর্ড চাইলে ছবিটা হালনাগাদ হয়।` }
        : { title: 'Evidence is getting old', text: `The newest purchase of ${s(f.shop_name)} is from ${fmtDate(s(f.newest))}, ${n(f.days)} days before the business calendar ends (the limit is ${n(f.limit_days)}). Recent records would bring the picture up to date.` }
    case 'consent_lapsed':
      return bn
        ? { title: 'বৈধ অনুমতি ছাড়া রেকর্ড', text: `${s(f.shop_name)}-এর রেকর্ড আছে, কিন্তু ${f.state === 'none' ? 'কোনো অনুমতি নেই' : 'অনুমতির মেয়াদ শেষ বা প্রত্যাহার হয়েছে'}। নতুন রেকর্ডের আগে আবার অনুমতি নিন।` }
        : { title: 'Records without a valid consent', text: `${s(f.shop_name)} has records but ${f.state === 'none' ? 'no consent' : 'its consent has expired or was revoked'}. Ask for consent again before adding records.` }
    default:
      return { title: issue.kind, text: '' }
  }
}

/** Where to act on an issue. */
export function actionsOf(issue: QualityIssueOut): { to: string; label: Pair }[] {
  const out: { to: string; label: Pair }[] = []
  const shop = (id: string | null | undefined, label: Pair) => id && out.push({ to: `/app/merchants/${encodeURIComponent(id)}`, label })
  if (issue.kind === 'possible_same_shop') {
    shop(issue.merchant_id, { en: `Open ${issue.merchant_id}`, bn: `${issue.merchant_id} খুলুন` })
    shop(issue.other_merchant_id, { en: `Open ${issue.other_merchant_id}`, bn: `${issue.other_merchant_id} খুলুন` })
    return out
  }
  if (issue.connection_id) {
    const matching = issue.kind === 'source_rows_left_out' || issue.kind === 'withdrawn_link'
    out.push({
      to: `/app/sources/${encodeURIComponent(issue.connection_id)}${matching ? '?tab=matching' : ''}`,
      label: matching ? { en: 'Open merchant matching', bn: 'মার্চেন্ট মেলানো খুলুন' } : { en: 'Open the connection', bn: 'সংযোগ খুলুন' },
    })
  }
  if (issue.batch_id) out.push({ to: `/app/imports/${encodeURIComponent(issue.batch_id)}`, label: { en: 'Open the import', bn: 'আমদানি খুলুন' } })
  shop(issue.merchant_id, { en: 'Open the merchant', bn: 'মার্চেন্ট খুলুন' })
  return out
}
