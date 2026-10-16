/**
 * The ten questionnaire items (FinHealth-style, each answered 1 to 5).
 *
 * The wording is kept in docs/QUESTIONNAIRE.md (the lead's file); this list must match it.
 * It is adapted from the four FinHealth Score indicators (Spend, Save, Borrow, Plan) to a
 * shop, plus two context items. The Bangla still needs a native-speaker review before the
 * demo: while it does, QUESTION_WORDING_IS_DRAFT stays true and the form says so.
 *
 * The keys are fixed by the API (QuestionnaireCreate in src/api/schemas.py).
 */
import type { QuestionnaireCreate } from '@/api/types'

export const QUESTION_WORDING_IS_DRAFT = true

export type ItemKey = keyof QuestionnaireCreate

export type Item = {
  key: ItemKey
  group: 'Spend' | 'Save' | 'Borrow' | 'Plan' | 'Context'
  en: string
  bn: string
  /** What 1 and 5 mean for this item, in English and Bangla. */
  low: string
  high: string
  lowBn: string
  highBn: string
}

const AGREE = {
  low: 'Not at all true',
  high: 'Completely true',
  lowBn: 'একদম সত্য নয়',
  highBn: 'পুরোপুরি সত্য',
}

export const ITEMS: Item[] = [
  {
    key: 'spend1',
    group: 'Spend',
    en: "Over the last month, the shop's money coming in was more than its spending.",
    bn: 'গত এক মাসে দোকানের আয় খরচের চেয়ে বেশি ছিল।',
    ...AGREE,
  },
  {
    key: 'spend2',
    group: 'Spend',
    en: 'The shop pays its suppliers and bills on time.',
    bn: 'দোকান সরবরাহকারীর টাকা ও বিল সময়মতো পরিশোধ করে।',
    ...AGREE,
  },
  {
    key: 'save1',
    group: 'Save',
    en: 'The shop has money set aside that could cover a bad month.',
    bn: 'একটি খারাপ মাস সামলানোর মতো টাকা দোকানের জমা আছে।',
    ...AGREE,
  },
  {
    key: 'save2',
    group: 'Save',
    en: 'The owner puts money aside regularly.',
    bn: 'মালিক নিয়মিত কিছু টাকা জমান।',
    ...AGREE,
  },
  {
    key: 'borrow1',
    group: 'Borrow',
    en: "The shop's current debts feel manageable.",
    bn: 'দোকানের এখনকার ঋণ সামলানো যায় বলে মনে হয়।',
    ...AGREE,
  },
  {
    key: 'borrow2',
    group: 'Borrow',
    en: 'The owner knows what the credit the shop uses costs.',
    bn: 'দোকান যে বাকি বা ঋণ নেয়, তার খরচ কত তা মালিক জানেন।',
    ...AGREE,
  },
  {
    key: 'plan1',
    group: 'Plan',
    en: "The owner plans ahead for the shop's money.",
    bn: 'মালিক দোকানের টাকাপয়সা নিয়ে আগে থেকে পরিকল্পনা করেন।',
    ...AGREE,
  },
  {
    key: 'plan2',
    group: 'Plan',
    en: 'The shop has a backup plan if sales drop.',
    bn: 'বিক্রি কমে গেলে দোকানের একটি বিকল্প পরিকল্পনা আছে।',
    ...AGREE,
  },
  // 1 = no stress, 5 = a lot of stress (src/synth/generate.py reverse-codes it: a reliable
  // merchant reports low stress). Keep this direction when the wording changes.
  {
    key: 'stress',
    group: 'Context',
    en: 'How much stress do money worries about the shop cause the owner?',
    bn: 'দোকানের টাকাপয়সা নিয়ে দুশ্চিন্তা মালিককে কতটা চাপে রাখে?',
    low: 'No stress',
    high: 'A lot of stress',
    lowBn: 'কোনো চাপ নেই',
    highBn: 'অনেক চাপ',
  },
  {
    key: 'confidence',
    group: 'Context',
    en: "The owner feels confident about the shop's finances for the coming year.",
    bn: 'আগামী এক বছরে দোকানের আর্থিক অবস্থা নিয়ে মালিক আত্মবিশ্বাসী।',
    ...AGREE,
  },
]
