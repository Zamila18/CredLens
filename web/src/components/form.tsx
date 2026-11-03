/**
 * Form controls: one look and one behaviour for every form in CredLens.
 *
 * - A Field gives its control a visible label, an optional hint, a required mark and an
 *   error, all tied to the control for screen readers (aria-describedby, aria-invalid).
 * - Controls are at least 44px tall (comfortable on a phone) and use the theme's focus ring.
 * - Errors say how to fix the problem; they never replace the label.
 */
import { createContext, useContext, useId, type ReactNode } from 'react'

import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'

type FieldIds = { id: string; describedBy?: string; invalid: boolean }
const FieldContext = createContext<FieldIds | null>(null)

/** The ids a control inside a Field needs. */
function useField(): FieldIds {
  const field = useContext(FieldContext)
  if (!field) throw new Error('A form control must sit inside a <Field>.')
  return field
}

export function Field({
  label,
  hint,
  error,
  required = false,
  children,
  className,
}: {
  label: string
  hint?: ReactNode
  error?: string | null
  required?: boolean
  children: ReactNode
  className?: string
}) {
  const t = useT()
  const id = useId()
  const labelSaysIt = /\((optional|required)\)|(ঐচ্ছিক|আবশ্যক)/i.test(label)
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined
  return (
    <FieldContext.Provider value={{ id, describedBy, invalid: Boolean(error) }}>
      <div className={cn('flex min-w-0 flex-col gap-1.5', className)}>
        <label htmlFor={id} className="text-sm font-semibold text-ink">
          {label}
          {/* A label that already says "(optional)" is not given the grey tag as well. */}
          {labelSaysIt ? null : required ? (
            <span className="ml-1 font-normal text-muted-2">({t('required', 'আবশ্যক')})</span>
          ) : (
            <span className="ml-1 font-normal text-muted-2">({t('optional', 'ঐচ্ছিক')})</span>
          )}
        </label>
        {hint && (
          <span id={hintId} className="text-[13px] leading-[19px] text-muted-2">
            {hint}
          </span>
        )}
        {children}
        {error && (
          <span id={errorId} className="text-[13px] leading-[19px] font-medium text-error">
            {error}
          </span>
        )}
      </div>
    </FieldContext.Provider>
  )
}

const control =
  'box-border min-h-11 w-full rounded-[10px] border bg-white px-3 text-[15px] text-ink placeholder:text-muted-2 disabled:bg-ground disabled:text-muted'

function controlClass(invalid: boolean, className?: string) {
  return cn(control, invalid ? 'border-error' : 'border-control-line hover:border-[#9fb6bd]', className)
}

export function TextInput(props: React.ComponentProps<'input'>) {
  const { id, describedBy, invalid } = useField()
  return (
    <input
      {...props}
      id={id}
      aria-describedby={describedBy}
      aria-invalid={invalid || undefined}
      className={controlClass(invalid, props.className)}
    />
  )
}

export function TextArea(props: React.ComponentProps<'textarea'>) {
  const { id, describedBy, invalid } = useField()
  return (
    <textarea
      rows={3}
      {...props}
      id={id}
      aria-describedby={describedBy}
      aria-invalid={invalid || undefined}
      className={controlClass(invalid, cn('py-2.5 leading-[22px]', props.className))}
    />
  )
}

export function Select({
  options,
  placeholder,
  ...props
}: React.ComponentProps<'select'> & { options: { value: string; label: string }[]; placeholder?: string }) {
  const { id, describedBy, invalid } = useField()
  return (
    <select
      {...props}
      id={id}
      aria-describedby={describedBy}
      aria-invalid={invalid || undefined}
      className={controlClass(invalid, props.className)}
    >
      {placeholder !== undefined && (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

/** Amounts in taka: a number pad on phones, the taka sign in front, no spinner arrows. */
export function MoneyInput(props: Omit<React.ComponentProps<'input'>, 'type'>) {
  const { id, describedBy, invalid } = useField()
  return (
    <div className="relative">
      <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-[15px] text-muted-2" aria-hidden="true">
        ৳
      </span>
      <input
        inputMode="decimal"
        autoComplete="off"
        {...props}
        id={id}
        type="text"
        aria-describedby={describedBy}
        aria-invalid={invalid || undefined}
        className={controlClass(invalid, cn('pl-7 tabular', props.className))}
      />
    </div>
  )
}

/**
 * A short set of choices shown as large radio options (easier to tap than a dropdown).
 * `options` stay few (2 to 6); use Select for long lists.
 */
export function ChoiceGroup({
  name,
  value,
  onChange,
  options,
  columns = 2,
}: {
  name: string
  value: string | null
  onChange: (value: string) => void
  options: { value: string; label: string; detail?: string }[]
  columns?: 1 | 2 | 3
}) {
  const { id, describedBy, invalid } = useField()
  return (
    <div
      role="radiogroup"
      aria-labelledby={undefined}
      aria-describedby={describedBy}
      aria-invalid={invalid || undefined}
      id={id}
      className={cn('grid gap-2', columns === 1 ? '' : columns === 2 ? 'sm:grid-cols-2' : 'sm:grid-cols-3')}
    >
      {options.map((option) => {
        const checked = value === option.value
        return (
          <label
            key={option.value}
            className={cn(
              'flex min-h-11 cursor-pointer items-start gap-3 rounded-[10px] border px-3 py-2.5 text-[15px]',
              checked ? 'border-lens bg-strong-selected' : 'border-control-line bg-white hover:bg-row-hover',
            )}
          >
            <input
              type="radio"
              aria-label={option.label}
              name={name}
              value={option.value}
              checked={checked}
              onChange={() => onChange(option.value)}
              className="mt-1 size-4 shrink-0 accent-[#00735a]"
            />
            <span className="flex flex-col">
              <span className="font-medium text-ink">{option.label}</span>
              {option.detail && <span className="text-[13px] text-muted-2">{option.detail}</span>}
            </span>
          </label>
        )
      })}
    </div>
  )
}

/** Several independent yes/no choices (for example the data categories of a consent). */
export function CheckList({
  values,
  onChange,
  options,
}: {
  values: string[]
  onChange: (values: string[]) => void
  options: { value: string; label: string; detail?: string }[]
}) {
  const { id, describedBy, invalid } = useField()
  const toggle = (value: string) =>
    onChange(values.includes(value) ? values.filter((v) => v !== value) : [...values, value])
  return (
    <div id={id} role="group" aria-describedby={describedBy} aria-invalid={invalid || undefined} className="grid gap-2 sm:grid-cols-2">
      {options.map((option) => {
        const checked = values.includes(option.value)
        return (
          <label
            key={option.value}
            className={cn(
              'flex min-h-11 cursor-pointer items-start gap-3 rounded-[10px] border px-3 py-2.5 text-[15px]',
              checked ? 'border-lens bg-strong-selected' : 'border-control-line bg-white hover:bg-row-hover',
            )}
          >
            <input type="checkbox" aria-label={option.label} checked={checked} onChange={() => toggle(option.value)} className="mt-1 size-4 shrink-0 accent-[#00735a]" />
            <span className="flex flex-col">
              <span className="font-medium text-ink">{option.label}</span>
              {option.detail && <span className="text-[13px] text-muted-2">{option.detail}</span>}
            </span>
          </label>
        )
      })}
    </div>
  )
}

/** The row of actions at the end of a form: the main action first, on the left. */
export function FormActions({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">{children}</div>
}
