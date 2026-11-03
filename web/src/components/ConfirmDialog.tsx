/**
 * Ask before a consequential action (recording consent, creating the one application).
 * Built on Radix Dialog: focus moves into the dialog, Escape cancels, focus returns after.
 * The confirm button shows that the action is running and cannot be pressed twice.
 */
import { Dialog } from 'radix-ui'
import type { ReactNode } from 'react'

import { useT } from '@/lib/i18n'
import { Button } from './ui/button'

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  children,
  confirmLabel,
  onConfirm,
  pending = false,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  children: ReactNode
  confirmLabel: string
  onConfirm: () => void
  pending?: boolean
}) {
  const t = useT()
  return (
    <Dialog.Root open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-ink/40" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 box-border flex w-[min(520px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 flex-col gap-4 rounded-card border border-card-line bg-white p-6 shadow-xl">
          <Dialog.Title className="m-0 font-display text-xl font-semibold text-ink">{title}</Dialog.Title>
          <Dialog.Description asChild>
            <div className="text-[15px] leading-[23px] text-ink-3">{children}</div>
          </Dialog.Description>
          <div className="flex flex-wrap justify-end gap-3 pt-2">
            <Dialog.Close asChild>
              <Button variant="outline" disabled={pending}>
                {t('Go back', 'ফিরে যান')}
              </Button>
            </Dialog.Close>
            <Button onClick={onConfirm} disabled={pending} aria-busy={pending}>
              {pending ? t('Saving…', 'সংরক্ষণ হচ্ছে…') : confirmLabel}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
