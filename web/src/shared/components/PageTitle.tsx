import type { ReactNode } from 'react'

/** The page's only <h1>, with its actions (children) aligned right. */
export function PageTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-page-title leading-tight font-semibold">{title}</h1>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  )
}
