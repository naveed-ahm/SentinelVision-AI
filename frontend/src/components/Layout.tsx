import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Activity, AlertTriangle, Bell, Camera, ChevronDown, CircuitBoard, ClipboardList,
  Gauge, LogOut, MapPin, MonitorPlay, Radio, Search, Settings, ShieldCheck, Siren, Users,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useLive } from "../context/LiveContext";
import { api } from "../api/client";
import type { AlertPage } from "../api/types";

const NAV = [
  { to: "/", label: "Overview", icon: Gauge, end: true },
  { to: "/monitoring", label: "Live Monitoring", icon: MonitorPlay },
  { to: "/cameras", label: "Camera Management", icon: Camera },
  { to: "/analytics", label: "AI Analytics", icon: CircuitBoard },
  { to: "/vehicles", label: "Vehicle Search", icon: Search },
  { to: "/watchlist", label: "Watchlist", icon: Siren },
  { to: "/tracking", label: "Vehicle Tracking", icon: Activity },
  { to: "/map", label: "GIS Map", icon: MapPin },
  { to: "/alerts", label: "Alerts", icon: Siren },
  { to: "/events", label: "Event History", icon: ClipboardList },
  { to: "/reports", label: "Reports", icon: ClipboardList },
  { to: "/health", label: "System Health", icon: ShieldCheck },
  { to: "/users", label: "User Management", icon: Users },
  { to: "/settings", label: "Settings", icon: Settings },
];

function Clock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="hidden lg:block text-right leading-tight">
      <p className="text-sm font-semibold tabular-nums">
        {now.toLocaleTimeString([], { hour12: false })}
      </p>
      <p className="text-[11px] text-muted">
        {now.toLocaleDateString([], { weekday: "short", day: "2-digit", month: "short", year: "numeric" })}
      </p>
    </div>
  );
}

function Notifications() {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState<AlertPage | null>(null);
  const { lastAlert, refreshKey } = useLive();
  const ref = useRef<HTMLDivElement>(null);

  const load = () => api.get<AlertPage>("/alerts", { params: { status: "open", page_size: 8 } })
    .then((r) => setAlerts(r.data))
    .catch(() => setAlerts(null));

  useEffect(() => {
    load();
  }, [refreshKey]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const count = alerts?.total ?? 0;
  return (
    <div className="relative" ref={ref}>
      <button
        className="relative rounded-md p-2 text-muted hover:text-body hover:bg-navy-600"
        onClick={() => {
          setOpen((o) => !o);
          if (!open) load();
        }}
        title="Notifications"
      >
        <Bell className="h-5 w-5" />
        {count > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] rounded-full bg-crit px-1 text-[10px] font-bold leading-[18px] text-white text-center">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-12 z-50 w-80 card p-0 overflow-hidden">
          <div className="card-header">
            <span className="card-title">Open alerts</span>
          </div>
          <div className="max-h-80 overflow-y-auto divide-y divide-slate-200">
            {(alerts?.items.length ?? 0) === 0 && (
              <p className="px-4 py-6 text-center text-xs text-muted">No open alerts</p>
            )}
            {alerts?.items.map((a) => (
              <div key={a.id} className="px-4 py-2.5 hover:bg-navy-600 cursor-pointer" onClick={() => (window.location.hash = `#/alerts?focus=${a.id}`)}>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm truncate">{a.title}</p>
                  <span className={`badge ${a.severity === "critical" ? "bg-crit/10 text-crit" : a.severity === "warning" ? "bg-warn/10 text-warn" : "bg-accent/10 text-accent-bright"}`}>
                    {a.severity}
                  </span>
                </div>
                <p className="text-[11px] text-muted">{a.created_at ? new Date(a.created_at).toLocaleString() : ""}</p>
              </div>
            ))}
          </div>
          <button
            className="w-full py-2 text-xs text-accent-bright hover:bg-navy-600"
            onClick={() => (window.location.hash = "#/alerts")}
          >
            View all alerts
          </button>
        </div>
      )}
      {lastAlert && <span className="sr-only">New alert: {lastAlert.title}</span>}
    </div>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { connected } = useLive();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="hidden md:flex w-60 shrink-0 flex-col bg-white border-r border-slate-200">
        <div className="flex items-center gap-2.5 px-4 h-14 border-b border-slate-200">
          <Radio className="h-6 w-6 text-accent" />
          <div>
            <p className="text-sm font-bold leading-tight">SentinelVision AI</p>
            <p className="text-[10px] text-muted tracking-wider uppercase">Command Center</p>
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto py-2">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-accent/10 text-accent-bright border-r-2 border-accent font-medium"
                    : "text-slate-600 hover:text-body hover:bg-navy-600 border-r-2 border-transparent"
                }`
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-slate-200 text-[11px] text-muted">
          <p className="flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-warn" />
            Hackathon proof of concept
          </p>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4">
          <div className="flex items-center gap-2 md:hidden">
            <Radio className="h-5 w-5 text-accent" />
            <span className="text-sm font-bold">SV AI</span>
          </div>
          <div className="flex-1" />
          <span
            className={`hidden sm:flex items-center gap-1.5 text-xs ${connected ? "text-ok" : "text-crit"}`}
            title={connected ? "Live updates connected" : "Live updates disconnected"}
          >
            <span className={`h-2 w-2 rounded-full ${connected ? "bg-ok animate-pulse" : "bg-crit"}`} />
            {connected ? "LIVE" : "OFFLINE"}
          </span>
          <Clock />
          <Notifications />
          <div className="relative" ref={menuRef}>
            <button
              className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-navy-600"
              onClick={() => setMenuOpen((o) => !o)}
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-xs font-bold text-white">
                {(user?.full_name || user?.username || "?").slice(0, 1).toUpperCase()}
              </div>
              <div className="hidden text-left leading-tight sm:block">
                <p className="text-xs font-semibold">{user?.full_name || user?.username}</p>
                <p className="text-[10px] text-muted capitalize">{user?.role}</p>
              </div>
              <ChevronDown className="h-4 w-4 text-muted" />
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-11 z-50 w-44 card overflow-hidden p-0">
                <button
                  className="flex w-full items-center gap-2 px-4 py-2.5 text-sm hover:bg-navy-600"
                  onClick={() => {
                    setMenuOpen(false);
                    logout();
                    navigate("/login");
                  }}
                >
                  <LogOut className="h-4 w-4" /> Logout
                </button>
              </div>
            )}
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
