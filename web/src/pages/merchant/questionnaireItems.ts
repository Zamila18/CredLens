/**
 * The ten questionnaire items (FinHealth-style, each answered 1 to 5).
 *
 * DRAFT WORDING. No approved wording for these items exists in the repo yet
 * (docs/DATASET_PLAN.md names the FinHealth Score Toolkit as the base). The lead
 * (Zamila) owns the final English text and the Bangla, which needs a native-speaker
 * review. Replace `en`, fill `bn`, and set QUESTION_WORDING_IS_DRAFT to false.
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
  /** Bangla text; empty until the reviewed wording arrives. */
  bn: string
  /** What 1 and 5 mean for this item. */
  low: string
  high: string
}

const AGREE = { low: 'Not at all true', high: 'Completely true' }

export const ITEMS: Item[] = [
  { key: 'spend1', group: 'Spend', en: "Over the last month, the shop's money coming in was more than its spending.", bn: '', ...AGREE },
  { key: 'spend2', group: 'Spend', en: 'The shop pays its suppliers and bills on time.', bn: '', ...AGREE },
  { key: 'save1', group: 'Save', en: 'The shop has money set aside that could cover a bad month.', bn: '', ...AGREE },
  { key: 'save2', group: 'Save', en: 'The owner puts money aside regularly.', bn: '', ...AGREE },
  { key: 'borrow1', group: 'Borrow', en: "The shop's current debts feel manageable.", bn: '', ...AGREE },
  { key: 'borrow2', group: 'Borrow', en: 'The owner knows what the credit the shop uses costs.', bn: '', ...AGREE },
  { key: 'plan1', group: 'Plan', en: "The owner plans ahead for the shop's money.", bn: '', ...AGREE },
  { key: 'plan2', group: 'Plan', en: 'The shop has a backup plan if sales drop.', bn: '', ...AGREE },
  { key: 'stress', group: 'Context', en: "Money worries about the shop cause the owner stress.", bn: '', ...AGREE },
  { key: 'confidence', group: 'Context', en: "The owner feels confident about the shop's finances for the coming year.", bn: '', ...AGREE },
]
