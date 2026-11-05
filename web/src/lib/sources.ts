/**
 * Where a record came from (the API's `source` keys), in order, with fixed colours and words.
 * Colours: validated categorical slots 1 to 4 (dataviz reference palette); generated is grey.
 */
import type { Pair } from '@/lib/i18n'

export const SOURCE_ORDER = ['receipts', 'typed_in', 'spreadsheet', 'data_source', 'data_file', 'generated'] as const

export const SOURCE_COLOR: Record<string, string> = {
  receipts: '#00735a',
  typed_in: '#2a78d6',
  spreadsheet: '#eb6834',
  data_source: '#1baf7a',
  data_file: '#eda100',
  generated: '#a3afb5',
}

export const SOURCE_WORDS: Record<string, Pair> = {
  receipts: { en: 'Checked receipts', bn: 'যাচাই করা রসিদ' },
  typed_in: { en: 'Typed in', bn: 'হাতে লেখা' },
  spreadsheet: { en: 'Spreadsheet', bn: 'স্প্রেডশিট' },
  data_source: { en: 'Data source', bn: 'ডেটার উৎস' },
  data_file: { en: 'Data file', bn: 'ডেটা ফাইল' },
  generated: { en: 'Generated', bn: 'তৈরি করা' },
}
