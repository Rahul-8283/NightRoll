import { useEffect } from 'react'
import Lenis from 'lenis'

// Smooth scrolling for the landing page only. The dashboard keeps native scrolling.
// Reduced-motion visitors get native scrolling too.
export function useLenis() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const lenis = new Lenis({
      duration: 1.15,
      easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      wheelMultiplier: 0.95,
    })

    let frame = 0
    const loop = (time: number) => {
      lenis.raf(time)
      frame = requestAnimationFrame(loop)
    }
    frame = requestAnimationFrame(loop)

    const anchors = (event: MouseEvent) => {
      const link = (event.target as HTMLElement).closest('a[href^="#"]') as HTMLAnchorElement | null
      if (!link) return
      const target = document.querySelector(link.getAttribute('href') as string)
      if (!target) return
      event.preventDefault()
      lenis.scrollTo(target as HTMLElement, { offset: -64 })
    }
    document.addEventListener('click', anchors)

    return () => {
      cancelAnimationFrame(frame)
      document.removeEventListener('click', anchors)
      lenis.destroy()
    }
  }, [])
}
