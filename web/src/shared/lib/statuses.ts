import type { Status } from '@/api/types'

interface StatusInfo {
  label: string
  // A Tailwind class, written out in full so Tailwind finds it.
  dotClass: string
}

/** Typed as a Record, so TypeScript fails when a status is missing. */
export const STATUSES: Record<Status, StatusInfo> = {
  acknowledged: { label: 'Acknowledged', dotClass: 'bg-status-acknowledged' },
  replied: { label: 'Replied', dotClass: 'bg-status-replied' },
  update: { label: 'Update', dotClass: 'bg-status-update' },
  rejected: { label: 'Rejected', dotClass: 'bg-status-rejected' },
}

/** Column order on the board, and option order in the status select. */
export const STATUS_ORDER: readonly Status[] = ['acknowledged', 'replied', 'update', 'rejected']
