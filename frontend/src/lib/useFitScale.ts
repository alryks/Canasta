import { useEffect, useState, type CSSProperties, type RefObject } from 'react'

interface FitLayout {
  scale: number
  shellHeight: number
}

interface UseFitScaleOptions {
  transformOrigin: string
  enabled?: boolean
}

export function useFitScale(
  containerRef: RefObject<HTMLElement | null>,
  contentRef: RefObject<HTMLElement | null>,
  deps: unknown[],
  { transformOrigin, enabled = true }: UseFitScaleOptions,
): { shellStyle: CSSProperties; contentStyle: CSSProperties } {
  const [layout, setLayout] = useState<FitLayout>({ scale: 1, shellHeight: 0 })

  useEffect(() => {
    if (!enabled) {
      setLayout({ scale: 1, shellHeight: 0 })
      return
    }

    const container = containerRef.current
    const content = contentRef.current
    if (!container || !content) return

    const update = () => {
      const contentWidth = content.scrollWidth
      const contentHeight = content.scrollHeight
      if (contentWidth === 0 || contentHeight === 0) {
        setLayout({ scale: 1, shellHeight: 0 })
        return
      }

      const width = container.clientWidth
      const height = container.clientHeight
      const scale =
        width === 0 || height === 0
          ? 1
          : Math.min(1, width / contentWidth, height / contentHeight)

      setLayout({
        scale,
        shellHeight: contentHeight * scale,
      })
    }

    update()
    const observer = new ResizeObserver(update)
    observer.observe(container)
    observer.observe(content)
    return () => observer.disconnect()
  }, [containerRef, contentRef, enabled, ...deps])

  const contentStyle: CSSProperties =
    layout.scale < 1
      ? {
          transform: `scale(${layout.scale})`,
          transformOrigin,
        }
      : {}

  const shellStyle: CSSProperties =
    layout.shellHeight > 0 ? { height: layout.shellHeight } : {}

  return { shellStyle, contentStyle }
}
