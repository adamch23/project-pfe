import { Routes, Route, Navigate } from "react-router-dom";
import { useContext } from "react";
import { AuthProvider, AuthContext } from "./context/AuthContext";
import { FaceGuardProvider } from "./context/FaceGuardContext";
import PrivateRoute from "./components/PrivateRoute";

import Login                      from "./pages/Login";
import Signup                     from "./pages/Signup";
import ForgotPassword             from "./pages/ForgotPassword";
import ResetPassword              from "./pages/ResetPassword";
import AdminDashboard             from "./pages/AdminDashboard";
import EmployerDashboard          from "./pages/EmployerDashboard";
import PersonalInfo               from "./pages/PersonalInfo";
import FaceVerify                 from "./pages/FaceVerify";
import PipelineFirewallDashboard  from "./pages/PipelineFirewallDashboard";
import DatabasePipelineDashboard  from "./pages/Databasepipelinedashboard";
import OSPipelineDashboard        from "./pages/OSPipelineDashboard";
import AppPipelineDashboard       from "./pages/AppPipelineDashboard";
import APILogsPipelineDashboard   from "./pages/Apilogspipelinedashboard";
import NotFound                   from "./pages/NotFound";

// ── Redirection intelligente à la racine ─────────────────────────
function RootRedirect() {
  const { user, loading } = useContext(AuthContext);

  if (loading) {
    return (
      <div style={{
        display: "flex", justifyContent: "center", alignItems: "center",
        height: "100vh", background: "#0a0a0f", color: "#FFC107",
        fontSize: "15px", letterSpacing: "2px", fontFamily: "sans-serif"
      }}>
        Chargement...
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;
  if (user.role === "admin") return <Navigate to="/admin" replace />;
  return <Navigate to="/dashboard" replace />;
}

function App() {
  return (
    <AuthProvider>
      {/*
       * FaceGuardProvider est DANS AuthProvider (il a besoin de `user`)
       * mais HORS des routes publiques (login, signup…)
       * Il démarre la surveillance uniquement quand un user est connecté.
       */}
      <FaceGuardProvider>
        <Routes>

          {/* ── Racine ── */}
          <Route path="/" element={<RootRedirect />} />

          {/* ── Pages publiques (pas de surveillance faciale) ── */}
          <Route path="/login"           element={<Login />} />
          <Route path="/signup"          element={<Signup />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password"  element={<ResetPassword />} />

          {/* ── Vérification faciale initiale (après login) ── */}
          <Route
            path="/face-verify"
            element={<PrivateRoute><FaceVerify /></PrivateRoute>}
          />

          {/* ── Profil personnel (admin + employer) ── */}
          <Route
            path="/profile"
            element={<PrivateRoute><PersonalInfo /></PrivateRoute>}
          />

          {/* ── Pipelines (admin + employer) ── */}
          <Route path="/PipelineFirewallDashboard"
            element={<PrivateRoute><PipelineFirewallDashboard /></PrivateRoute>} />
          <Route path="/DatabasePipelineDashboard"
            element={<PrivateRoute><DatabasePipelineDashboard /></PrivateRoute>} />
          <Route path="/OSPipelineDashboard"
            element={<PrivateRoute><OSPipelineDashboard /></PrivateRoute>} />
          <Route path="/AppPipelineDashboard"
            element={<PrivateRoute><AppPipelineDashboard /></PrivateRoute>} />
          <Route path="/APILogsPipelineDashboard"
            element={<PrivateRoute><APILogsPipelineDashboard /></PrivateRoute>} />

          {/* ── Admin uniquement ── */}
          <Route path="/admin"
            element={<PrivateRoute role="admin"><AdminDashboard /></PrivateRoute>} />

          {/* ── Employer uniquement ── */}
          <Route path="/dashboard"
            element={<PrivateRoute role="employer"><EmployerDashboard /></PrivateRoute>} />

          {/* ── 404 ── */}
          <Route path="/404" element={<NotFound />} />
          <Route path="*"    element={<Navigate to="/404" replace />} />

        </Routes>
      </FaceGuardProvider>
    </AuthProvider>
  );
}

export default App;