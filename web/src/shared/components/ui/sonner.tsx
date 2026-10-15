import type * as React from 'react'
import { Toaster as Sonner, type ToasterProps } from 'sonner'

// shadcn's version reads the theme from next-themes. Jats is light only, so it is fixed here.
function Toaster(props: ToasterProps) {
  return (
    <Sonner
      theme="light"
      className="toaster group"
      style={
        {
          '--normal-bg': 'var(--popover)',
          '--normal-text': 'var(--popover-foreground)',
          '--normal-border': 'var(--border)',
          '--border-radius': 'var(--radius)',
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
