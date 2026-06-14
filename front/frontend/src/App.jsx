import { Routes, Route, Navigate } from "react-router-dom";
import { useContext } from "react";
import { AuthProvider, AuthContext } from "./context/AuthContext";
import { FaceGuardProvider } from "./context/FaceGuardContext";
import PrivateRoute from "./components/PrivateRoute";

// Features: Auth
import Login from "./features/auth/pages/Login/Login";
import Signup from "./features/auth/pages/Signup/Signup";
import ForgotPassword from "./features/auth/pages/ForgotPassword/ForgotPassword";
import ResetPassword from "./features/auth/pages/ResetPassword/ResetPassword";

// Features: Users
import AdminDashboard from "./features/users/pages/AdminDashboard/AdminDashboard";
import EmployerDashboard from "./features/users/pages/EmployerDashboard/EmployerDashboard";
import PersonalInfo from "./features/users/pages/PersonalInfo/PersonalInfo";

// Features: Face Verify
import FaceVerify from "./features/face-verify/pages/FaceVerify/FaceVerify";

// Features: Pipelines
import PipelineFirewallDashboard from "./features/pipelines/pages/FirewallPipeline/FirewallPipeline";
import DatabasePipelineDashboard from "./features/pipelines/pages/DatabasePipeline/DatabasePipeline";
import OSPipelineDashboard from "./features/pipelines/pages/OsPipeline/OsPipeline";
import AppPipelineDashboard from "./features/pipelines/pages/AppPipeline/AppPipeline";
import APILogsPipelineDashboard from "./features/pipelines/pages/ApiLogsPipeline/ApiLogsPipeline";
import AnomalyDashboard from "./features/pipelines/pages/AnomalyPage";
import MonitoringDashboard from "./features/monitoring/pages/MonitoringDashboard";

// Features: Core
import NotFound from "./features/core/pages/NotFound/NotFound";

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
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />

          {/* ── Vérification faciale initiale (après login) ── */}
          <Route
            path="/face-verify"
            element={<PrivateRoute><FaceVerify /></PrivateRoute>}
          />

          {/* ── Profil personnel (admin + analyste) ── */}
          <Route
            path="/profile"
            element={<PrivateRoute><PersonalInfo /></PrivateRoute>}
          />

          {/* ── Pipelines (admin + analyste) ── */}
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
          <Route path="/AnomalyDashboard"
            element={<PrivateRoute><AnomalyDashboard /></PrivateRoute>} />
          <Route path="/MonitoringDashboard"
            element={<PrivateRoute><MonitoringDashboard /></PrivateRoute>} />

          {/* ── Admin uniquement ── */}
          <Route path="/admin"
            element={<PrivateRoute role="admin"><AdminDashboard /></PrivateRoute>} />

          {/* ── Analyste uniquement ── */}
          <Route path="/dashboard"
            element={<PrivateRoute role="analyste"><EmployerDashboard /></PrivateRoute>} />

          {/* ── 404 ── */}
          <Route path="/404" element={<NotFound />} />
          <Route path="*" element={<Navigate to="/404" replace />} />

        </Routes>
      </FaceGuardProvider>
    </AuthProvider>
  );
}

export default App;