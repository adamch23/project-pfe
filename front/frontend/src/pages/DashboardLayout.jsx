/**
 * DashboardLayout.jsx — mis à jour
 * ─────────────────────────────────────────────────────────────
 * Ajouts :
 *  - Bouton ON/OFF surveillance faciale dans la Navbar
 *  - Overlay AccessBlocked quand le visage n'est plus détecté
 * ─────────────────────────────────────────────────────────────
 */
import { useContext } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { AuthContext } from "../context/AuthContext";
import { useFaceGuard } from "../context/FaceGuardContext";
import AccessBlocked from "./AccessBlocked";
import './dashboard.css';

const Sidebar = ({ userRole }) => (
  <aside className="sidebar">
    <div className="sidebar-header">
      <span className="brand-main">Attijari</span><span className="brand-sub">bank</span>
    </div>
    <nav className="sidebar-menu">
      <NavLink to="/AppPipelineDashboard" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
        <span className="menu-icon">🖥️</span> App Pipeline
      </NavLink>
      <NavLink to="/APILogsPipelineDashboard" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
        <span className="menu-icon">🔌</span> API Pipeline
      </NavLink>
      <NavLink to="/OSPipelineDashboard" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
        <span className="menu-icon">⚙️</span> OS Pipeline
      </NavLink>
      <NavLink to="/DatabasePipelineDashboard" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
        <span className="menu-icon">🗄️</span> Database Pipeline
      </NavLink>
      <NavLink to="/PipelineFirewallDashboard" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
        <span className="menu-icon">🔥</span> Firewall Pipeline
      </NavLink>

      {userRole === "admin" && (
        <NavLink to="/admin" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
          <span className="menu-icon">🛡️</span> Administration
        </NavLink>
      )}

      <NavLink to="/profile" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
        <span className="menu-icon">👤</span> Mon Profil
      </NavLink>
    </nav>
    <div className="sidebar-footer">
      <p>© 2026 Attijariwafa Bank</p>
    </div>
  </aside>
);

const Navbar = ({ user, logout }) => {
  const { isGuardActive, hasFacePhoto, toggleGuard } = useFaceGuard();

  return (
    <header className="navbar">
      <div className="nav-search-container">
        <div className="search-bar">
          <span className="search-icon">🔍</span>
          <input type="text" placeholder="Rechercher un service..." />
        </div>
      </div>

      <div className="nav-right-side">

        {/* ── Bouton surveillance faciale ── */}
        {hasFacePhoto && (
          <button
            className={`face-guard-toggle ${isGuardActive ? "face-guard-toggle--on" : "face-guard-toggle--off"}`}
            onClick={toggleGuard}
            title={isGuardActive ? "Désactiver la surveillance faciale" : "Activer la surveillance faciale"}
          >
            <span className="fgt-icon">
              {isGuardActive ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              )}
            </span>
            <span className="fgt-label">
              {isGuardActive ? "Surveillance ON" : "Surveillance OFF"}
            </span>
            <span className={`fgt-dot ${isGuardActive ? "fgt-dot--on" : "fgt-dot--off"}`} />
          </button>
        )}

        {/* ── Avatar / profil ── */}
        <NavLink to="/profile" style={{ textDecoration: "none" }}>
          <div className="user-profile-card">
            <div className="user-details">
              <span className="u-name">{user?.name || "Utilisateur"}</span>
              <span className="u-email">{user?.email || ""}</span>
              <span className="u-role-badge">{user?.role || ""}</span>
            </div>
            <div className="u-avatar">
              {user?.name?.charAt(0) || "U"}
            </div>
          </div>
        </NavLink>

        <button onClick={logout} className="logout-action-btn">
          Déconnexion
        </button>
      </div>
    </header>
  );
};

export default function DashboardLayout({ children }) {
  const { user, logout } = useContext(AuthContext);
  const { isBlocked }    = useFaceGuard();
  const navigate         = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="dashboard-app-container">
      <Sidebar userRole={user?.role} />
      <main className="dashboard-main">
        <Navbar user={user} logout={handleLogout} />
        <div className="dashboard-content-scroll">
          {children}
        </div>
      </main>

      {/* ── Overlay blocage facial ── */}
      {isBlocked && <AccessBlocked />}
    </div>
  );
}