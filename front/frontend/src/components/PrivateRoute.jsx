import { Navigate } from "react-router-dom";
import { useContext } from "react";
import { AuthContext } from "../context/AuthContext";

export default function PrivateRoute({ children, role }) {
  const { user, loading } = useContext(AuthContext);

  if (loading) {
    return (
      <div style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        height: "100vh",
        background: "#0a0a0f",
        fontFamily: "sans-serif",
        color: "#FFC107",
        fontSize: "15px",
        letterSpacing: "2px",
      }}>
        Chargement...
      </div>
    );
  }

  // Pas connecté → login
  if (!user) return <Navigate to="/login" replace />;

  // Connecté mais rôle insuffisant → 404
  if (role && user.role !== role) return <Navigate to="/404" replace />;

  return children;
}