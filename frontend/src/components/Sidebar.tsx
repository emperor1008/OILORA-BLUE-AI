"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Plus,
  FolderOpen,
  Settings,
  Activity,
  Anchor,
} from "lucide-react";
import { clsx } from "clsx";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "New Investigation", href: "/new", icon: Plus },
];

const secondaryNav = [
  { name: "System Status", href: "/status", icon: Activity },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex flex-col w-60 bg-ocean-midnight text-white min-h-screen">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-ocean-deep">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-ocean-blue to-ocean-aqua flex items-center justify-center">
            <Anchor className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight leading-none">
              OILORA BLUE AI
            </h1>
            <p className="text-[10px] text-ocean-aqua/70 mt-0.5 tracking-wide">
              Maritime Intelligence
            </p>
          </div>
        </div>
      </div>

      {/* Primary navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navigation.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.name}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-ocean-blue/20 text-ocean-aqua"
                  : "text-gray-300 hover:bg-white/5 hover:text-white",
              )}
            >
              <item.icon className="w-4 h-4 shrink-0" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* Secondary navigation */}
      <div className="px-3 pb-4 space-y-1 border-t border-ocean-deep pt-4">
        {secondaryNav.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.name}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-ocean-blue/20 text-ocean-aqua"
                  : "text-gray-300 hover:bg-white/5 hover:text-white",
              )}
            >
              <item.icon className="w-4 h-4 shrink-0" />
              {item.name}
            </Link>
          );
        })}
      </div>

      {/* Local demo badge */}
      <div className="px-5 py-4 border-t border-ocean-deep">
        <div className="flex items-center gap-2 text-xs text-ocean-muted">
          <div className="w-2 h-2 rounded-full bg-ocean-success animate-pulse" />
          Local Demo Mode
        </div>
      </div>
    </aside>
  );
}
