"use client";

import { Menu, Anchor } from "lucide-react";
import Link from "next/link";

interface HeaderProps {
  onMenuToggle?: () => void;
}

export default function Header({ onMenuToggle }: HeaderProps) {
  return (
    <header className="h-14 bg-white border-b border-ocean-border flex items-center px-4 lg:px-6 shrink-0">
      {/* Mobile menu button */}
      <button
        onClick={onMenuToggle}
        className="lg:hidden p-2 -ml-2 mr-2 text-ocean-muted hover:text-ocean-slate"
        aria-label="Toggle navigation menu"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Mobile brand */}
      <div className="lg:hidden flex items-center gap-2">
        <div className="w-7 h-7 rounded-md bg-gradient-to-br from-ocean-blue to-ocean-aqua flex items-center justify-center">
          <Anchor className="w-4 h-4 text-white" />
        </div>
        <span className="text-sm font-bold text-ocean-midnight">OILORA BLUE AI</span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Right side */}
      <div className="flex items-center gap-3 text-xs text-ocean-muted">
        <span className="hidden sm:inline">Local Demo Mode</span>
        <div className="w-2 h-2 rounded-full bg-ocean-success" title="System online" />
      </div>
    </header>
  );
}
