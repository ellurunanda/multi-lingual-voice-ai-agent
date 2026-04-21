import { useState } from "react";
import { LayoutDashboard, Mic, Calendar, Menu, X, Activity, Stethoscope } from "lucide-react";
import { VoiceAgentPage } from "./pages/VoiceAgentPage.jsx";
import { AppointmentsPage } from "./pages/AppointmentsPage.jsx";
import { DashboardPage } from "./pages/DashboardPage.jsx";

const NAV_ITEMS = [
  { id: "voice", label: "Voice Agent", icon: Mic, badge: "LIVE" },
  { id: "appointments", label: "Appointments", icon: Calendar },
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
];

const PAGE_MAP = {
  voice: VoiceAgentPage,
  appointments: AppointmentsPage,
  dashboard: DashboardPage,
};

export default function App() {
  const [activePage, setActivePage] = useState("voice");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const ActivePage = PAGE_MAP[activePage];

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 lg:hidden backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-30 w-64 flex flex-col transition-transform duration-300 ease-in-out ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
        style={{ background: "linear-gradient(180deg, #0f172a 0%, #1e293b 100%)" }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 py-5 border-b border-white/10">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center shadow-lg"
            style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}>
            <Stethoscope className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="font-bold text-white text-sm leading-tight tracking-wide">ClinicalAI</p>
            <p className="text-xs text-slate-400 mt-0.5">Voice Appointment Agent</p>
          </div>
          <button
            className="ml-auto lg:hidden text-slate-400 hover:text-white transition-colors"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-5 space-y-1">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest px-3 mb-3">Navigation</p>
          {NAV_ITEMS.map(({ id, label, icon: Icon, badge }) => (
            <button
              key={id}
              onClick={() => { setActivePage(id); setSidebarOpen(false); }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group ${
                activePage === id
                  ? "text-white shadow-lg"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
              style={activePage === id ? { background: "linear-gradient(135deg, #3b82f6, #6366f1)" } : {}}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="flex-1 text-left">{label}</span>
              {badge && (
                <span className="text-xs px-1.5 py-0.5 rounded-full font-semibold"
                  style={{ background: "#22c55e20", color: "#22c55e" }}>
                  {badge}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-white/10">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-xs text-slate-400">System Online</span>
          </div>
          <p className="text-xs text-slate-500">Multilingual: EN · HI · TA · TE</p>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile top bar */}
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-slate-200 bg-white shadow-sm">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-slate-500 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}>
              <Activity className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-slate-900 text-sm">
              {NAV_ITEMS.find((n) => n.id === activePage)?.label}
            </span>
          </div>
        </div>

        {/* Page */}
        <main className="flex-1 overflow-hidden">
          <ActivePage />
        </main>
      </div>
    </div>
  );
}