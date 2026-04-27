import { useAuth } from "../lib/auth";

const NAV = [
  { id: "dashboard", label: "Dashboard", icon: "🏠" },
  { id: "setup", label: "New Interview", icon: "✨" },
  { id: "history", label: "History", icon: "📋" },
  { id: "scoreboard", label: "Scoreboard", icon: "📊" },
];

export default function NavBar({ active, onNavigate }) {
  const { user, logout } = useAuth();
  return (
    <nav className="bg-white/80 backdrop-blur border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <button
          onClick={() => onNavigate("dashboard")}
          className="flex items-center gap-2 text-slate-800 font-semibold"
        >
          <span className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-500 to-violet-600 flex items-center justify-center text-white text-sm">
            AI
          </span>
          <span className="hidden sm:inline">Interview Platform</span>
        </button>
        <div className="flex items-center gap-1">
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={
                "px-3 py-1.5 rounded-lg text-sm font-medium transition flex items-center gap-1.5 " +
                (active === item.id
                  ? "bg-brand-50 text-brand-700"
                  : "text-slate-600 hover:bg-slate-100")
              }
            >
              <span>{item.icon}</span>
              <span className="hidden md:inline">{item.label}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden sm:block text-sm text-slate-600">
            👤 {user?.username}
          </span>
          <button
            onClick={logout}
            className="text-sm text-slate-500 hover:text-slate-800 px-2 py-1 rounded-md hover:bg-slate-100 transition"
          >
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
}
