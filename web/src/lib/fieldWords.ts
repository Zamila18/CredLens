/**
 * Plain words for the choices of the field forms. The choices themselves come from the API
 * (GET /demo/settings, which reads the config); only their wording lives here.
 * A choice without wording here is shown as the API names it, so nothing disappears.
 */
import type { Pair } from './i18n'

type Words = Pair & { detail?: Pair }

export const CATEGORY_WORDS: Record<string, Words> = {
  purchases: {
    en: 'Stock purchases',
    bn: 'মাল কেনা',
    detail: { en: 'What the shop buys from its suppliers (not its sales).', bn: 'দোকান সরবরাহকারীর কাছ থেকে যা কেনে (বিক্রি নয়)।' },
  },
  deliveries: {
    en: 'Parcel deliveries',
    bn: 'পার্সেল ডেলিভারি',
    detail: { en: 'Parcels the shop sends to its own customers, if it sells that way.', bn: 'দোকান নিজের ক্রেতাদের যে পার্সেল পাঠায়, যদি এভাবে বিক্রি করে।' },
  },
  payments: {
    en: 'Repayments of earlier loans',
    bn: 'আগের ঋণের পরিশোধ',
    detail: { en: 'Instalments of loans the shop already had.', bn: 'দোকানের আগের ঋণের কিস্তি।' },
  },
  questionnaire: {
    en: 'Money-habits questions',
    bn: 'টাকা-পয়সার অভ্যাসের প্রশ্ন',
    detail: { en: 'Ten short questions; they never change the score.', bn: 'দশটি ছোট প্রশ্ন; স্কোরে কখনো প্রভাব ফেলে না।' },
  },
  field_visits: {
    en: 'Field visit notes',
    bn: 'মাঠ পরিদর্শনের নোট',
    detail: { en: 'Short notes from staff visits to the shop.', bn: 'দোকানে কর্মীর পরিদর্শনের ছোট নোট।' },
  },
}

export const METHOD_WORDS: Record<string, Words> = {
  assisted_on_phone: {
    en: 'Shown on the phone and explained',
    bn: 'ফোনে দেখিয়ে বুঝিয়ে বলা হয়েছে',
    detail: { en: 'The merchant read this screen with you.', bn: 'মার্চেন্ট আপনার সাথে এই পর্দা পড়েছেন।' },
  },
  paper_form_reference: {
    en: 'Paper form',
    bn: 'কাগজের ফর্ম',
    detail: { en: 'The merchant signed a paper form; keep its reference.', bn: 'মার্চেন্ট কাগজের ফর্মে সই করেছেন; রেফারেন্স রাখুন।' },
  },
  verbal_recorded_by_staff: {
    en: 'Said aloud, recorded by staff',
    bn: 'মুখে বলেছেন, কর্মী লিখেছেন',
    detail: { en: 'The weakest record of an answer; use only when nothing else is possible.', bn: 'উত্তরের সবচেয়ে দুর্বল রেকর্ড; অন্য উপায় না থাকলেই।' },
  },
}

export const PURPOSE_WORDS: Record<string, Words> = {
  inventory_restock: { en: 'Restock the shop', bn: 'দোকানে মাল তোলা' },
  seasonal_stock: { en: 'Seasonal stock (for example Eid)', bn: 'মৌসুমি মাল (যেমন ঈদ)' },
  shop_equipment: { en: 'Shop equipment', bn: 'দোকানের সরঞ্জাম' },
  other: { en: 'Something else', bn: 'অন্য কিছু' },
}

export const OUTCOME_WORDS: Record<string, Words> = {
  shop_open_trading: { en: 'Shop open and trading', bn: 'দোকান খোলা, বেচাকেনা চলছে' },
  owner_not_available: { en: 'Owner not available', bn: 'মালিক নেই' },
  shop_closed: { en: 'Shop closed', bn: 'দোকান বন্ধ' },
  follow_up_needed: { en: 'Follow-up needed', bn: 'আবার যেতে হবে' },
}

export const DELIVERY_STATUS_WORDS: Record<string, Words> = {
  delivered: { en: 'Delivered', bn: 'পৌঁছেছে' },
  returned: { en: 'Returned', bn: 'ফেরত এসেছে' },
  failed: { en: 'Failed', bn: 'ব্যর্থ' },
  cancelled: { en: 'Cancelled', bn: 'বাতিল' },
}

export const RETURN_REASON_WORDS: Record<string, Words> = {
  refused: { en: 'Customer refused it', bn: 'ক্রেতা নেননি' },
  wrong_item: { en: 'Wrong item', bn: 'ভুল জিনিস' },
  address_issue: { en: 'Address problem (courier side)', bn: 'ঠিকানার সমস্যা (কুরিয়ারের দিক)' },
  rider_issue: { en: 'Rider problem (courier side)', bn: 'রাইডারের সমস্যা (কুরিয়ারের দিক)' },
  other: { en: 'Other', bn: 'অন্য' },
}

export const SHOP_TYPE_WORDS: Record<string, Words> = {
  grocery: { en: 'Grocery', bn: 'মুদি' },
  pharmacy: { en: 'Pharmacy', bn: 'ফার্মেসি' },
  apparel: { en: 'Clothing', bn: 'কাপড়' },
  electronics: { en: 'Electronics', bn: 'ইলেকট্রনিক্স' },
  other: { en: 'Other', bn: 'অন্য' },
}

export const NEXT_STEP_WORDS: Record<string, Pair> = {
  record_consent: { en: 'Next: record consent', bn: 'পরের ধাপ: অনুমতি নিন' },
  add_records: { en: 'Next: add records', bn: 'পরের ধাপ: রেকর্ড যোগ করুন' },
  create_application: { en: 'Next: create the application', bn: 'পরের ধাপ: আবেদন তৈরি করুন' },
  await_review: { en: 'Waiting for the officer’s review', bn: 'কর্মকর্তার পর্যালোচনার অপেক্ষায়' },
}

/** The words for a value, or the value itself when no wording exists. */
export function wordsFor(map: Record<string, Words>, value: string, lang: 'en' | 'bn'): string {
  const words = map[value]
  return words ? words[lang] : value.replaceAll('_', ' ')
}

/** The detail sentence for a value, if any. */
export function detailFor(map: Record<string, Words>, value: string, lang: 'en' | 'bn'): string | undefined {
  return map[value]?.detail?.[lang]
}
