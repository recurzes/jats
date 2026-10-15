import { useCallback } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router'

export const APP_PARAM = 'app'

// Marks a history entry that `open` pushed, so `close` can step back over it.
interface PanelState {
  openedPanel?: boolean
}

/**
 * The open application lives in the URL (`/?app=<id>`), so a refresh keeps the panel open and
 * Back closes it. Other search parameters are kept.
 */
export function useSelectedApp() {
  const [searchParams, setSearchParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const id = searchParams.get(APP_PARAM) || null
  const openedHere = (location.state as PanelState | null)?.openedPanel === true

  const open = useCallback(
    (nextId: string) => {
      setSearchParams(
        (previous) => {
          const next = new URLSearchParams(previous)
          next.set(APP_PARAM, nextId)
          return next
        },
        { state: { openedPanel: true } satisfies PanelState },
      )
    },
    [setSearchParams],
  )

  const close = useCallback(() => {
    // Opened from the board: going back keeps history the same as pressing Back.
    if (openedHere) {
      void navigate(-1)
      return
    }
    // Arrived with ?app= already set (a refresh or a shared link): drop it in place.
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        next.delete(APP_PARAM)
        return next
      },
      { replace: true },
    )
  }, [openedHere, navigate, setSearchParams])

  return { id, open, close }
}
