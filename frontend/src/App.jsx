import { useState } from "react";
import { AuthProvider, useAuth } from "./lib/auth";
import { FullScreenSpinner } from "./components/Spinner";
import NavBar from "./components/NavBar";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Setup from "./pages/Setup";
import Interview from "./pages/Interview";
import Feedback from "./pages/Feedback";
import History from "./pages/History";
import HistoryDetail from "./pages/HistoryDetail";
import Scoreboard from "./pages/Scoreboard";

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}

function Shell() {
  const { user, loading } = useAuth();
  // screen state
  const [screen, setScreen] = useState("dashboard");
  // ephemeral state for active flows
  const [activeSession, setActiveSession] = useState(null);
  const [lastSummary, setLastSummary] = useState(null);
  const [openHistory, setOpenHistory] = useState(null); // { sessionId, grade }

  if (loading) return <FullScreenSpinner label="Restoring your session…" />;
  if (!user) return <Login />;

  // The interview & feedback screens don't show NavBar (immersive).
  if (screen === "interview" && activeSession) {
    return (
      <Interview
        session={activeSession}
        onFinish={(summary) => {
          setLastSummary(summary);
          setActiveSession(null);
          setScreen("feedback");
        }}
        onCancel={() => {
          setActiveSession(null);
          setScreen("dashboard");
        }}
      />
    );
  }
  if (screen === "feedback" && lastSummary) {
    return (
      <div className="min-h-screen">
        <NavBar
          active="feedback"
          onNavigate={(s) => {
            setScreen(s);
          }}
        />
        <Feedback
          summary={lastSummary}
          onNavigate={(s) => {
            if (s === "setup") setLastSummary(null);
            setScreen(s);
          }}
        />
      </div>
    );
  }

  // Standard navigation chrome
  return (
    <div className="min-h-screen pb-12">
      <NavBar active={screen} onNavigate={(s) => { setOpenHistory(null); setScreen(s); }} />
      {screen === "dashboard" && <Dashboard onNavigate={setScreen} />}
      {screen === "setup" && (
        <Setup
          onStart={(s) => {
            setActiveSession(s);
            setScreen("interview");
          }}
        />
      )}
      {screen === "history" && !openHistory && (
        <History
          onOpen={(sessionId, grade) => setOpenHistory({ sessionId, grade })}
        />
      )}
      {screen === "history" && openHistory && (
        <HistoryDetail
          sessionId={openHistory.sessionId}
          grade={openHistory.grade}
          onBack={() => setOpenHistory(null)}
        />
      )}
      {screen === "scoreboard" && <Scoreboard />}
    </div>
  );
}
