import { BookOpen, LayoutDashboard, LifeBuoy, ListChecks, LogOut, PlusCircle, Wifi, WifiOff } from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { useTicketSocket } from "../../hooks/useTicketSocket";
import type { Role } from "../../types";
import { cn } from "../../utils/cn";
import { PageSkeleton } from "../common/ui";

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  end?: boolean;
}

const NAV: Record<Role, NavItem[]> = {
  AUTHOR: [
    { to: "/author", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" />, end: true },
    { to: "/author/books", label: "My Books", icon: <BookOpen className="h-4 w-4" /> },
    { to: "/author/tickets/new", label: "New Query", icon: <PlusCircle className="h-4 w-4" /> },
    { to: "/author/tickets", label: "My Tickets", icon: <LifeBuoy className="h-4 w-4" />, end: true },
  ],
  ADMIN: [
    { to: "/admin", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" />, end: true },
    { to: "/admin/tickets", label: "Ticket Queue", icon: <ListChecks className="h-4 w-4" /> },
  ],
};

export function homePathFor(role: Role): string {
  return role === "ADMIN" ? "/admin" : "/author";
}

/** Route guard + chrome. The backend enforces RBAC; this only keeps the UI honest. */
export function ProtectedLayout({ role }: { role: Role }) {
  const { user, loading, logout } = useAuth();
  const socketStatus = useTicketSocket(user !== null);

  if (loading) return <div className="p-10"><PageSkeleton /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={homePathFor(user.role)} replace />;

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="flex items-center gap-2 px-5 py-5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-white"><BookOpen className="h-4 w-4" /></span>
          <div>
            <p className="text-sm font-bold leading-tight">BookLeaf</p>
            <p className="text-[11px] text-slate-500">{role === "ADMIN" ? "Support Console" : "Author Portal"}</p>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-3" aria-label="Main">
          {NAV[role].map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn("flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition", isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100")
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-100 p-4">
          <p className="truncate text-sm font-medium">{user.author?.name ?? "Support Admin"}</p>
          <p className="truncate text-xs text-slate-500">{user.email}</p>
          <div className="mt-3 flex items-center justify-between">
            <span className={cn("inline-flex items-center gap-1 text-[11px]", socketStatus === "open" ? "text-emerald-600" : "text-slate-400")} title="Live updates">
              {socketStatus === "open" ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
              {socketStatus === "open" ? "Live" : "Offline"}
            </span>
            <button onClick={logout} className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-900">
              <LogOut className="h-3.5 w-3.5" /> Sign out
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:hidden">
          <span className="text-sm font-bold">BookLeaf</span>
          <nav className="flex gap-3 text-xs font-medium">
            {NAV[role].map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => (isActive ? "text-brand-700" : "text-slate-500")}>
                {item.label}
              </NavLink>
            ))}
            <button onClick={logout} className="text-slate-500">Sign out</button>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-8 md:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
