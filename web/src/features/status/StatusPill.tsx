import type { ComponentProps } from 'react'
import { cn } from '@/shared/lib/utils'

export type StatusTone = 'good' | 'warning' | 'error'

const DOT: Record<StatusTone, string> = {
  good: 'bg-good',
  warning: 'bg-warning',
  error: 'bg-error',
}

/**
 * A coloured dot and a label. The text must carry the meaning on its own: the dot is only a hint.
 * Extra props reach the outer span, so it can be a tooltip trigger.
 */
export function StatusPill({
  tone,
  className,
  children,
  ...props
}: ComponentProps<'span'> & { tone: StatusTone }) {
  return (
    <span
      data-tone={tone}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border bg-surface px-2.5 py-1 text-label whitespace-nowrap text-ink',
        className,
      )}
      {...props}
    >
      <span aria-hidden className={cn('size-2 shrink-0 rounded-full', DOT[tone])} />
      {children}
    </span>
  )
}
