/**
 * What the public pages say about data sources and the pipeline. Every status is the true
 * state of this build: "available" means it works in the app today, "file" means the data
 * arrives through a file import, "partial" means part of the stage exists, "planned" means
 * it is designed but not built or not connected. No partnership is implied by a name.
 */
import type { LucideIcon } from 'lucide-react'
import {
  Building2,
  Calculator,
  ClipboardPen,
  CreditCard,
  FileSpreadsheet,
  Network,
  ShoppingCart,
  Store,
  Truck,
  Wallet,
} from 'lucide-react'

export type Availability = 'available' | 'file' | 'partial' | 'planned'

export const AVAILABILITY: Record<Availability, { en: string; bn: string; tone: string }> = {
  available: { en: 'Available', bn: 'চালু', tone: 'border-mint-line bg-mint-2 text-lens-dark' },
  file: { en: 'Available through file import', bn: 'ফাইল আমদানির মাধ্যমে চালু', tone: 'border-mint-line bg-mint-2 text-lens-dark' },
  partial: { en: 'Partly built', bn: 'আংশিক তৈরি', tone: 'border-amber-chip bg-amber-panel text-amber-text' },
  planned: { en: 'Planned · not connected', bn: 'পরিকল্পিত · সংযুক্ত নয়', tone: 'border-line bg-neutral-chip text-neutral-text' },
}

export const SOURCES: { icon: LucideIcon; status: Availability; en: string; bn: string; textEn: string; textBn: string; examplesEn?: string; examplesBn?: string }[] = [
  {
    icon: ClipboardPen,
    status: 'available',
    en: 'Field collection',
    bn: 'মাঠ থেকে সংগ্রহ',
    textEn: 'Staff register a shop, record consent, purchases, deliveries, repayments and visits on a phone.',
    textBn: 'কর্মী ফোনে দোকান নিবন্ধন, অনুমতি, কেনাকাটা, ডেলিভারি, পরিশোধ ও পরিদর্শন রাখেন।',
  },
  {
    icon: FileSpreadsheet,
    status: 'available',
    en: 'Spreadsheets',
    bn: 'স্প্রেডশিট',
    textEn: 'Upload an Excel purchase sheet, match its columns, check every row, then save.',
    textBn: 'এক্সেল কেনাকাটার শিট তুলুন, কলাম মেলান, প্রতিটি সারি দেখুন, তারপর রাখুন।',
  },
  {
    icon: Building2,
    status: 'file',
    en: 'Institutional records',
    bn: 'প্রতিষ্ঠানের নিজস্ব রেকর্ড',
    textEn: 'An institution’s own merchant, loan and repayment files, loaded in a documented format.',
    textBn: 'প্রতিষ্ঠানের নিজস্ব মার্চেন্ট, ঋণ ও পরিশোধের ফাইল, নির্দিষ্ট ফরম্যাটে।',
  },
  {
    icon: ShoppingCart,
    status: 'planned',
    en: 'Wholesale and commerce platforms',
    bn: 'পাইকারি ও কমার্স প্ল্যাটফর্ম',
    textEn: 'Stock orders placed by the shop on a B2B platform.',
    textBn: 'B2B প্ল্যাটফর্মে দোকানের দেওয়া মালের অর্ডার।',
    examplesEn: 'For example ShopUp / Mokam',
    examplesBn: 'যেমন ShopUp / Mokam',
  },
  {
    icon: Wallet,
    status: 'planned',
    en: 'Shop-credit services',
    bn: 'দোকান-ঋণ সেবা',
    textEn: 'Earlier credit lines and their repayments.',
    textBn: 'আগের ঋণ ও তার পরিশোধ।',
    examplesEn: 'For example Baki',
    examplesBn: 'যেমন Baki',
  },
  {
    icon: Truck,
    status: 'planned',
    en: 'Logistics',
    bn: 'লজিস্টিকস',
    textEn: 'Parcels the shop sends, delivered or returned, and cash collected on delivery.',
    textBn: 'দোকানের পাঠানো পার্সেল, পৌঁছানো বা ফেরত, আর ডেলিভারিতে নেওয়া টাকা।',
    examplesEn: 'For example REDX',
    examplesBn: 'যেমন REDX',
  },
  { icon: Store, status: 'planned', en: 'Retail POS', bn: 'রিটেইল POS', textEn: 'Sales-side records from a point-of-sale system.', textBn: 'পয়েন্ট-অফ-সেল সিস্টেমের বিক্রির রেকর্ড।' },
  { icon: Network, status: 'planned', en: 'Distributor systems', bn: 'ডিস্ট্রিবিউটর সিস্টেম', textEn: 'Orders and deliveries recorded by a distributor.', textBn: 'ডিস্ট্রিবিউটরের রাখা অর্ডার ও ডেলিভারি।' },
  { icon: Calculator, status: 'planned', en: 'Accounting software', bn: 'হিসাব-সফটওয়্যার', textEn: 'Books kept by the business or its accountant.', textBn: 'ব্যবসা বা তার হিসাবরক্ষকের রাখা খাতা।' },
  { icon: CreditCard, status: 'planned', en: 'Payment records', bn: 'পেমেন্ট রেকর্ড', textEn: 'Payments received and made through a provider.', textBn: 'কোনো প্রোভাইডারের মাধ্যমে নেওয়া ও দেওয়া পেমেন্ট।' },
]

export const STAGES: { en: string; bn: string; status: Availability; textEn: string; textBn: string; todayEn: string; todayBn: string }[] = [
  {
    en: 'Business sources',
    bn: 'ব্যবসার উৎস',
    status: 'partial',
    textEn: 'Evidence starts where the business already keeps it: memo books, spreadsheets, an institution’s files, or connected systems.',
    textBn: 'প্রমাণ শুরু হয় যেখানে ব্যবসা তা রাখে: মেমো-খাতা, স্প্রেডশিট, প্রতিষ্ঠানের ফাইল, বা সংযুক্ত সিস্টেম।',
    todayEn: 'Field entry, Excel purchase sheets and institutional files work today. Platform connectors are planned.',
    todayBn: 'মাঠের এন্ট্রি, এক্সেল কেনাকাটার শিট ও প্রতিষ্ঠানের ফাইল আজ চালু। প্ল্যাটফর্ম সংযোগ পরিকল্পিত।',
  },
  {
    en: 'Ingestion',
    bn: 'গ্রহণ',
    status: 'available',
    textEn: 'Records enter through one checked path: a form, a previewed import, or a file load.',
    textBn: 'রেকর্ড আসে একটি যাচাইকৃত পথে: ফর্ম, দেখে-নেওয়া আমদানি, বা ফাইল লোড।',
    todayEn: 'Every path checks dates, amounts, consent and the business calendar before anything is saved.',
    todayBn: 'কিছু রাখার আগে প্রতিটি পথ তারিখ, অঙ্ক, অনুমতি ও ব্যবসার ক্যালেন্ডার যাচাই করে।',
  },
  {
    en: 'Identity matching',
    bn: 'পরিচয় মেলানো',
    status: 'partial',
    textEn: 'Records are tied to the right merchant. A likely duplicate is shown to a person, never merged automatically.',
    textBn: 'রেকর্ড সঠিক মার্চেন্টের সাথে যুক্ত হয়। সম্ভাব্য দ্বৈত মানুষকে দেখানো হয়, নিজে থেকে একীকরণ হয় না।',
    todayEn: 'Duplicate warnings on shop registration and repeated rows on import. A full match-review queue is being built.',
    todayBn: 'দোকান নিবন্ধনে ও আমদানির পুনরাবৃত্ত সারিতে দ্বৈত সতর্কতা। পূর্ণ মিল-পর্যালোচনার তালিকা তৈরি হচ্ছে।',
  },
  {
    en: 'Normalisation',
    bn: 'একরূপ করা',
    status: 'available',
    textEn: 'Purchases, deliveries, repayments and visits each keep their own meaning in one consistent structure.',
    textBn: 'কেনাকাটা, ডেলিভারি, পরিশোধ ও পরিদর্শন নিজ নিজ অর্থ রেখে এক ধরনের কাঠামোয় থাকে।',
    todayEn: 'Each kind of record has its own validated structure; nothing is flattened into one ambiguous transaction.',
    todayBn: 'প্রতিটি রেকর্ডের নিজস্ব যাচাইকৃত কাঠামো; কিছুই এক অস্পষ্ট লেনদেনে মেশানো হয় না।',
  },
  {
    en: 'Provenance',
    bn: 'উৎস-চিহ্ন',
    status: 'available',
    textEn: 'Every record says how it entered, who entered it, when, and what is known about it.',
    textBn: 'প্রতিটি রেকর্ড বলে কীভাবে এলো, কে রাখলেন, কখন, আর এ সম্পর্কে কী জানা আছে।',
    todayEn: 'Entry method, actor, real time, business date, import batch and status on every record.',
    todayBn: 'প্রতিটি রেকর্ডে এন্ট্রির ধরন, কে, আসল সময়, ব্যবসার তারিখ, আমদানির ব্যাচ ও অবস্থা।',
  },
  {
    en: 'Assessment',
    bn: 'মূল্যায়ন',
    status: 'available',
    textEn: 'A model reads the organised evidence and returns a score with its coverage and exact reasons.',
    textBn: 'মডেল গোছানো প্রমাণ পড়ে কভারেজ ও সঠিক কারণসহ স্কোর দেয়।',
    todayEn: 'A logistic-regression model, validated on synthetic data only. Missing data never lowers a score.',
    todayBn: 'লজিস্টিক রিগ্রেশন মডেল, শুধু সিনথেটিক ডেটায় যাচাই করা। তথ্য না থাকলে স্কোর কমে না।',
  },
  {
    en: 'Evidence review',
    bn: 'প্রমাণ পর্যালোচনা',
    status: 'available',
    textEn: 'Fixed checks say whether a file is ready for review and the smallest evidence to ask for.',
    textBn: 'নির্দিষ্ট যাচাই বলে ফাইল পর্যালোচনার জন্য প্রস্তুত কি না, আর ন্যূনতম কী প্রমাণ চাইতে হবে।',
    todayEn: 'Review status, open checks and evidence requests, kept apart from the score.',
    todayBn: 'পর্যালোচনার অবস্থা, বাকি যাচাই ও প্রমাণের অনুরোধ, স্কোর থেকে আলাদা।',
  },
  {
    en: 'Human decision',
    bn: 'মানুষের সিদ্ধান্ত',
    status: 'available',
    textEn: 'An authorised officer decides. An override needs a written reason, and the record keeps what was on screen.',
    textBn: 'অনুমোদিত কর্মকর্তা সিদ্ধান্ত নেন। পরিবর্তনে লিখিত কারণ লাগে, আর রেকর্ডে তখনকার পর্দার তথ্য থাকে।',
    todayEn: 'Append-only decisions and an audit log of every read and write.',
    todayBn: 'শুধু-যোগ করা যায় এমন সিদ্ধান্ত, আর প্রতিটি দেখা ও লেখার অডিট লগ।',
  },
]
