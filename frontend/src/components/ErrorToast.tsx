import { AnimatePresence, motion } from 'framer-motion'
import { useEffect } from 'react'
import { isOpeningThresholdRollback, translateActionError } from '../lib/errors'

const AUTO_DISMISS_MS = 6000

interface ErrorToastProps {
  reason: string | null
  onDismiss: () => void
  offsetForBanner?: boolean
}

// Single floating toast for action_error messages: translated to Russian,
// slides in from the top, auto-dismisses (or on click).
export function ErrorToast({ reason, onDismiss, offsetForBanner = false }: ErrorToastProps) {
  const isRollback = isOpeningThresholdRollback(reason)

  useEffect(() => {
    if (reason === null) return
    const id = setTimeout(onDismiss, AUTO_DISMISS_MS)
    return () => clearTimeout(id)
  }, [reason, onDismiss])

  return (
    <AnimatePresence>
      {reason !== null && (
        <motion.div
          key={reason}
          className={`error-toast${offsetForBanner ? ' is-below-banner' : ''}${
            isRollback ? ' is-rollback-notice' : ''
          }`}
          role="alert"
          initial={{ opacity: 0, y: -24, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -16, scale: 0.96 }}
          transition={{ type: 'spring', stiffness: 420, damping: 30 }}
        >
          <span className="error-toast-icon" aria-hidden>
            {isRollback ? '↩' : '⚠'}
          </span>
          <span className="error-toast-copy">
            <strong>{isRollback ? 'Карты вернулись' : 'Не получилось'}</strong>
            <span className="error-toast-text">{translateActionError(reason)}</span>
          </span>
          <button
            type="button"
            className="error-toast-close"
            aria-label="Закрыть"
            onClick={onDismiss}
          >
            ✕
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
