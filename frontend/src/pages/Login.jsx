import { useEffect, useState } from "react";
import { useAuth } from "../lib/auth";

export default function Login() {
  const [tab, setTab] = useState("login"); // 'login' | 'register'
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [apiReachable, setApiReachable] = useState(true);
  const { login, register } = useAuth();

  // Probe the API on mount so we can show a clear banner rather than letting
  // users fill out forms before discovering the backend is down.
  useEffect(() => {
    let cancelled = false;
    const base = (import.meta.env.VITE_API_URL || "") + "/api/v1";
    fetch(base + "/health", { credentials: "include" })
      .then((r) => {
        if (!cancelled) setApiReachable(r.ok);
      })
      .catch(() => {
        if (!cancelled) setApiReachable(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!username.trim() || !password) {
      setError("Username and password are required.");
      return;
    }
    if (password.length < 4) {
      setError("Password must be at least 4 characters.");
      return;
    }
    if (tab === "register" && password !== confirm) {
      setError("Passwords don't match.");
      return;
    }

    setLoading(true);
    try {
      if (tab === "login") await login(username.trim(), password);
      else await register(username.trim(), password);
    } catch (e) {
      setError(e.message.replace(/^\d+:\s*/, ""));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 animate-fade-in">
      <div className="w-full max-w-md">
        {/* Brand */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-500 to-violet-600 text-white text-2xl font-bold shadow-lg mb-3">
            AI
          </div>
          <h1 className="text-2xl font-bold text-slate-800">Interview Platform</h1>
          <p className="text-sm text-slate-500 mt-1">
            Practice domain-aware interviews with instant feedback.
          </p>
        </div>

        {!apiReachable && (
          <div className="mb-4 bg-amber-50 border border-amber-200 text-amber-800 rounded-xl px-4 py-3 text-sm">
            <div className="font-semibold">Backend not reachable</div>
            <div className="text-xs mt-1 leading-relaxed">
              Start the API in another terminal:
              <code className="block mt-1 px-2 py-1 bg-amber-100 rounded">uvicorn api.main:app --reload</code>
            </div>
          </div>
        )}

        {/* Card */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          {/* Tabs */}
          <div className="flex bg-slate-100 rounded-xl p-1 mb-5">
            <button
              onClick={() => { setTab("login"); setError(null); }}
              className={
                "flex-1 py-2 text-sm font-medium rounded-lg transition " +
                (tab === "login"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700")
              }
            >
              Log In
            </button>
            <button
              onClick={() => { setTab("register"); setError(null); }}
              className={
                "flex-1 py-2 text-sm font-medium rounded-lg transition " +
                (tab === "register"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700")
              }
            >
              Register
            </button>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="text-sm font-medium text-slate-700">Username</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                placeholder="your username"
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2.5 bg-slate-50 focus:bg-white focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none transition"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={tab === "login" ? "current-password" : "new-password"}
                placeholder="••••••"
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2.5 bg-slate-50 focus:bg-white focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none transition"
              />
            </div>
            {tab === "register" && (
              <div>
                <label className="text-sm font-medium text-slate-700">Confirm password</label>
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  autoComplete="new-password"
                  placeholder="••••••"
                  className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2.5 bg-slate-50 focus:bg-white focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none transition"
                />
              </div>
            )}

            {error && (
              <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-brand-600 to-violet-600 text-white font-medium shadow-sm hover:shadow-md disabled:opacity-50 transition"
            >
              {loading ? "Please wait…" : tab === "login" ? "Log In" : "Create Account"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-400 mt-4">
          By continuing you agree to use this practice tool responsibly.
        </p>
      </div>
    </div>
  );
}
