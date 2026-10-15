/**
 * Button: the shadcn/ui button, restyled to the CredLens design.
 *
 * - primary: lens-green "Record decision" / "Check file" button (Merchant.dc.html .primary)
 * - outline: white button with lens-green text ("Open ›", "Record new answers")
 * - ghost:   no border, for small inline actions
 * There is no red "destructive" variant: the design has no red anywhere.
 */
import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { Slot } from 'radix-ui'

import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 font-sans font-semibold whitespace-nowrap transition-colors disabled:cursor-not-allowed [&_svg]:pointer-events-none [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        primary:
          'border-0 bg-lens text-white hover:bg-lens-dark disabled:bg-disabled disabled:text-ground',
        outline:
          'border border-button-line bg-card text-lens hover:bg-open-hover hover:text-lens-hover disabled:text-muted',
        ghost: 'border-0 bg-transparent text-lens hover:bg-open-hover',
      },
      size: {
        sm: 'min-h-10 rounded-lg px-3.5 text-[13px]',
        md: 'min-h-11 rounded-[10px] px-4 text-sm',
        lg: 'min-h-12 rounded-[10px] px-5 text-[15px]',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : 'button'

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button }
