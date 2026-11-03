/**
 * Reveal: fades its children up once, the first time they scroll into view. Without
 * IntersectionObserver (or with reduced motion, handled in index.css) it just shows them.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

export function Reveal({ children, className, as: Tag = 'div', delay = 0 }: { children: ReactNode; className?: string; as?: 'div' | 'section' | 'li'; delay?: number }) {
  const ref = useRef<HTMLElement | null>(null)
  const [visible, setVisible] = useState(() => typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    const node = ref.current
    if (!node || visible) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.08 },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [visible])
  return (
    <Tag ref={ref as never} className={cn('reveal', visible && 'is-visible', className)} style={delay ? { transitionDelay: `${delay}ms` } : undefined}>
      {children}
    </Tag>
  )
}
