// Centralised API client. ALL components import from here.
// Cookies are sent automatically because we use credentials:'include'.
//
// In dev the Vite proxy forwards /api/* to localhost:8000, so a relative
// base just works. In prod, set VITE_API_URL=https://your-api.example.com
// at build time so the static frontend can call the API on a different host.

const BASE = (import.meta.env.VITE_API_URL || "") + "/api/v1";

async function jsonFetch(path, options = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch (networkErr) {
    // fetch() itself threw — backend unreachable, CORS blocked, etc.
    const e = new Error(
      "Cannot reach the API server. Make sure the backend is running on " +
      "port 8000 (uvicorn api.main:app --reload)."
    );
    e.cause = networkErr;
    throw e;
  }

  if (res.status === 204) return null;

  let body = null;
  let raw = "";
  try {
    raw = await res.text();
    body = raw ? JSON.parse(raw) : null;
  } catch (_) {
    body = null;
  }

  if (!res.ok) {
    let msg = body && (body.detail || body.message);

    // 404s are extra-confusing. Disambiguate them:
    //   - backend up, route missing → JSON body with detail
    //   - backend down, Vite proxy returned its own 404 → plain HTML or empty
    if (res.status === 404 && !msg) {
      msg =
        "The API server isn't reachable. Start the backend with " +
        "'uvicorn api.main:app --reload' on port 8000, then try again.";
    }
    if (!msg) msg = res.statusText || `HTTP ${res.status}`;

    // Log to console so the failing URL is visible in DevTools.
    console.error(
      `[api] ${options.method || "GET"} ${BASE + path} → ${res.status}`,
      body || raw
    );

    const err = new Error(`${res.status}: ${msg}`);
    err.status = res.status;
    err.body = body;
    err.url = BASE + path;
    throw err;
  }

  return body;
}

export const api = {
  // ---- Auth ----
  register: (username, password) =>
    jsonFetch("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  login: (username, password) =>
    jsonFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => jsonFetch("/auth/logout", { method: "POST" }),
  me: () => jsonFetch("/auth/me"),

  // ---- Catalogue ----
  topics: () => jsonFetch("/topics"),

  // ---- Interview lifecycle ----
  createSession: (body) =>
    jsonFetch("/session", { method: "POST", body: JSON.stringify(body) }),
  generateQuestion: (session_id, qtype = null) =>
    jsonFetch("/generate-question", {
      method: "POST",
      body: JSON.stringify({ session_id, qtype }),
    }),
  evaluateAnswer: (session_id, question_id, answer) =>
    jsonFetch("/evaluate-answer", {
      method: "POST",
      body: JSON.stringify({ session_id, question_id, answer }),
    }),
  generateScenario: (session_id, topic = null) =>
    jsonFetch("/generate-scenario", {
      method: "POST",
      body: JSON.stringify({ session_id, topic }),
    }),
  endSession: (session_id) =>
    jsonFetch(`/session/${session_id}/end`, { method: "POST" }),

  // ---- History / dashboard / scoreboard ----
  dashboard: () => jsonFetch("/history/dashboard"),
  grades: () => jsonFetch("/history/grades"),
  gradeQuestions: (session_id) => jsonFetch(`/history/grades/${session_id}/questions`),
  topicStats: () => jsonFetch("/history/topic-stats"),
};
