import type { ReactNode } from 'react'

/** The page's only <h1>, a small mono note beside it (meta), and its actions (children) aligned right. */
export function PageTitle({
  title,
  meta,
  children,
}: {
  title: string
  meta?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-baseline gap-3">
        <h1 className="text-page-title leading-tight font-semibold">{title}</h1>
        {meta && <span className="font-mono text-label text-muted">{meta}</span>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  )
}
