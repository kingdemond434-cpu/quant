"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  Boxes,
  Cpu,
  LayoutDashboard,
  ShieldAlert,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/research", label: "Research", icon: BarChart3 },
  { href: "/portfolio", label: "Portfolio", icon: Boxes },
  { href: "/risk", label: "Risk", icon: ShieldAlert },
  { href: "/execution", label: "Execution", icon: Cpu },
  { href: "/monitoring", label: "Monitoring", icon: Activity },
];

export function Nav() {
  const path = usePathname();
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-panel">
      <div className="flex items-center gap-2 px-4 py-4">
        <div className="h-2 w-2 rounded-full bg-accent shadow-[0_0_8px] shadow-accent" />
        <span className="text-sm font-semibold tracking-tight">QUANT&nbsp;DESK</span>
      </div>
      <nav className="flex flex-col gap-0.5 px-2">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                active
                  ? "bg-panel2 text-fg"
                  : "text-muted hover:bg-panel2/60 hover:text-fg",
              )}
            >
              <Icon size={15} className={active ? "text-accent" : ""} />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto px-4 py-3 text-[10px] leading-relaxed text-muted">
        Read-only view. No live capital is allocated automatically.
      </div>
    </aside>
  );
}
