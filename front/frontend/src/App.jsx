import { Routes, Route, Navigate } from "react-router-dom";
import { useContext } from "react";
import { AuthProvider, AuthContext } from "./context/AuthContext";
import PrivateRoute from "./components/PrivateRoute";

// Pages publiques
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";

// Dashboards
import AdminDashboard from "./pages/AdminDashboard";
import EmployerDashboard from "./pages/EmployerDashboard";

// Pipelines
import PipelineFirewallDashboard from "./pages/PipelineFirewallDashboard";
import DatabasePipelineDashboard from "./pages/Databasepipelinedashboard";
import OSPipelineDashboard from "./pages/OSPipelineDashboard";
import AppPipelineDashboard from "./pages/AppPipelineDashboard";
import APILogsPipelineDashboard from "./pages/Apilogspipelinedashboard";

// New Profile Page
import PersonalInfo from "./pages/PersonalInfo";

// Autres
import NotFound from "./pages/NotFound";


// ─────────────────────────────────────────────
// Redirection intelligente selon le rôle
// ─────────────────────────────────────────────
function RootRedirect() {
  const { user, loading } = useContext(AuthContext);

  if (loading) {
    return (
      <div style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        height: "100vh",
        background: "#0a0a0f",
        color: "#FFC107",
        fontSize: "15px",
        letterSpacing: "2px",
      }}>
        Chargement...
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;
  if (user.role === "admin") return <Navigate to="/admin" replace />;
  return <Navigate to="/dashboard" replace />;
}


// ─────────────────────────────────────────────
// APP
// ─────────────────────────────────────────────
function App() {
  return (
    <AuthProvider>
      <Routes>

        {/* ── Racine ── */}
        <Route path="/" element={<RootRedirect />} />

        {/* ── Pages publiques ── */}
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />

        {/* ── Page profil (admin + employer) ── */}
        <Route
          path="/profile"
          element={
            <PrivateRoute>
              <PersonalInfo />
            </PrivateRoute>
          }
        />

        {/* ── Pipelines (accessible à tous les users connectés) ── */}
        <Route
          path="/PipelineFirewallDashboard"
          element={
            <PrivateRoute>
              <PipelineFirewallDashboard />
            </PrivateRoute>
          }
        />

        <Route
          path="/DatabasePipelineDashboard"
          element={
            <PrivateRoute>
              <DatabasePipelineDashboard />
            </PrivateRoute>
          }
        />

        <Route
          path="/OSPipelineDashboard"
          element={
            <PrivateRoute>
              <OSPipelineDashboard />
            </PrivateRoute>
          }
        />

        <Route
          path="/AppPipelineDashboard"
          element={
            <PrivateRoute>
              <AppPipelineDashboard />
            </PrivateRoute>
          }
        />

        <Route
          path="/APILogsPipelineDashboard"
          element={
            <PrivateRoute>
              <APILogsPipelineDashboard />
            </PrivateRoute>
          }
        />

        {/* ── Admin uniquement ── */}
        <Route
          path="/admin"
          element={
            <PrivateRoute role="admin">
              <AdminDashboard />
            </PrivateRoute>
          }
        />

        {/* ── Employer uniquement ── */}
        <Route
          path="/dashboard"
          element={
            <PrivateRoute role="employer">
              <EmployerDashboard />
            </PrivateRoute>
          }
        />

        {/* ── 404 ── */}
        <Route path="/404" element={<NotFound />} />

        {/* ── Toute route inconnue ── */}
        <Route path="*" element={<Navigate to="/404" replace />} />

      </Routes>
    </AuthProvider>
  );
}

export default App;