"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";

/**
 * Barra de progreso global para navegaciones entre rutas.
 * - Se dispara al click en cualquier <a href> interno.
 * - Se completa cuando usePathname() cambia (Next terminó la navegación).
 * - Usa un "avance simulado" (stepper) para dar sensación de progreso.
 */
export function NavigationProgress() {
  const pathname = usePathname();
  const [progress, setProgress] = useState<number | null>(null);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  function clearTimers() {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  }

  // Al cambiar pathname: completar y ocultar
  useEffect(() => {
    if (progress === null) return;
    clearTimers();
    setProgress(100);
    const t = setTimeout(() => setProgress(null), 220);
    timersRef.current.push(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  // Interceptar clicks en links internos
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (e.defaultPrevented) return;
      if (e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

      const target = e.target as HTMLElement | null;
      const anchor = target?.closest("a[href]") as HTMLAnchorElement | null;
      if (!anchor) return;

      const href = anchor.getAttribute("href");
      if (!href) return;
      if (href.startsWith("#")) return;
      if (/^[a-z]+:\/\//i.test(href)) return; // externos
      if (anchor.target === "_blank") return;
      if (anchor.hasAttribute("download")) return;

      // Misma ruta: no iniciamos
      try {
        const url = new URL(anchor.href, window.location.origin);
        if (url.pathname === pathname) return;
      } catch { /* ignore */ }

      clearTimers();
      setProgress(15);
      timersRef.current.push(setTimeout(() => setProgress(45), 120));
      timersRef.current.push(setTimeout(() => setProgress(70), 400));
      timersRef.current.push(setTimeout(() => setProgress(88), 900));
    }

    document.addEventListener("click", onClick, { capture: true });
    return () => document.removeEventListener("click", onClick, { capture: true } as any);
  }, [pathname]);

  useEffect(() => () => clearTimers(), []);

  if (progress === null) return null;

  return (
    <div
      aria-hidden
      className="fixed top-0 left-0 right-0 z-[100] h-0.5 bg-primary/10 pointer-events-none"
    >
      <div
        className="h-full bg-primary shadow-[0_0_8px_rgba(59,130,246,0.6)] transition-[width] duration-200 ease-out"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
