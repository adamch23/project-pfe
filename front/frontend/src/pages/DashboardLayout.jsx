// DashboardLayout.jsx - Version avec animations 3D + Logo
import { useContext, useState, useEffect } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { AuthContext } from "../context/AuthContext";
import { useFaceGuard } from "../context/FaceGuardContext";
import AccessBlocked from "../pages/AccessBlocked";
import './dashboard.css';
import LogoImg from "../Images/Logo_Attijari_bank.png";

const Sidebar = ({ userRole }) => {
  const [hoveredItem, setHoveredItem] = useState(null);
  
  const menuItems = [
    { path: "/AppPipelineDashboard", icon: "🖥️", label: "App Pipeline" },
    { path: "/APILogsPipelineDashboard", icon: "🔌", label: "API Pipeline" },
    { path: "/OSPipelineDashboard", icon: "⚙️", label: "OS Pipeline" },
    { path: "/DatabasePipelineDashboard", icon: "🗄️", label: "Database Pipeline" },
    { path: "/PipelineFirewallDashboard", icon: "🔥", label: "Firewall Pipeline" },
    { path: "/AnomalyDashboard", icon: "⚠️", label: "Anomaly Dashboard" }

  ];

  return (
    <aside className="sidebar">
      {/* LOGO à la place du texte Attijaribank */}
      <div className="sidebar-header">
        <div className="sidebar-logo-wrap">
          <img src={LogoImg} alt="Attijari bank" className="sidebar-logo-img" />
        </div>
      </div>
      <nav className="sidebar-menu">
        {menuItems.map((item, index) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => (isActive ? "menu-item active" : "menu-item")}
            onMouseEnter={() => setHoveredItem(index)}
            onMouseLeave={() => setHoveredItem(null)}
            style={{
              transitionDelay: `${index * 0.05}s`,
              transform: hoveredItem === index ? 'translateX(8px)' : 'none'
            }}
          >
            <span className="menu-icon">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
        {userRole === "admin" && (
          <NavLink
            to="/admin"
            className={({ isActive }) => (isActive ? "menu-item active" : "menu-item")}
          >
            <span className="menu-icon">🛡️</span>
            <span>Administration</span>
          </NavLink>
        )}
        <NavLink
          to="/profile"
          className={({ isActive }) => (isActive ? "menu-item active" : "menu-item")}
        >
          <span className="menu-icon">👤</span>
          <span>Mon Profil</span>
        </NavLink>
      </nav>
      <div className="sidebar-footer">
        <p>© 2026 Attijariwafa Bank</p>
        <p style={{ fontSize: '9px', marginTop: '8px', opacity: 0.5 }}>Version 3.0 - Sécurisé par IA</p>
      </div>
    </aside>
  );
};

const Navbar = ({ user, logout }) => {
  const { isGuardActive, hasFacePhoto, toggleGuard } = useFaceGuard();
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const formatTime = () => {
    return currentTime.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <header className="navbar">
      <div className="search-bar">
        <span className="search-icon">🔍</span>
        <input type="text" placeholder="Rechercher un service, un pipeline..." />
      </div>

      <div className="nav-right-side">
        <div style={{ fontSize: '12px', color: 'var(--atj-text-muted)' }}>
          {formatTime()}
        </div>

        {hasFacePhoto && (
          <button
            className={`face-guard-toggle ${isGuardActive ? "face-guard-toggle--on" : "face-guard-toggle--off"}`}
            onClick={toggleGuard}
            title={isGuardActive ? "Désactiver la surveillance faciale" : "Activer la surveillance faciale"}
          >
            <span className="fgt-icon">
              {isGuardActive ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              )}
            </span>
            <span className="fgt-label">
              {isGuardActive ? "Surveillance ON" : "Surveillance OFF"}
            </span>
            <span className={`fgt-dot ${isGuardActive ? "fgt-dot--on" : "fgt-dot--off"}`} />
          </button>
        )}

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

// Composant pour les cartes statistiques avec animation
export const StatCard = ({ title, value, icon, trend, trendValue, delay }) => {
  return (
    <div className="stat-card" style={{ animationDelay: `${delay}s` }}>
      <div className="stat-card-header">
        <span className="stat-card-title">{title}</span>
        <div className="stat-card-icon">{icon}</div>
      </div>
      <div className="stat-card-value">{value}</div>
      {trend && (
        <div className="stat-card-trend">
          <span className={trend === 'up' ? 'trend-up' : 'trend-down'}>
            {trend === 'up' ? '↑' : '↓'} {trendValue}%
          </span>
          <span style={{ fontSize: '10px', color: 'var(--atj-text-muted)' }}>
            vs mois dernier
          </span>
        </div>
      )}
    </div>
  );
};

export default function DashboardLayout({ children }) {
  const { user, logout } = useContext(AuthContext);
  const { isBlocked } = useFaceGuard();
  const navigate = useNavigate();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  // Effet de chargement progressif
  useEffect(() => {
    const mainContent = document.querySelector('.dashboard-content-scroll');
    if (mainContent) {
      mainContent.style.opacity = '0';
      setTimeout(() => {
        mainContent.style.transition = 'opacity 0.5s ease';
        mainContent.style.opacity = '1';
      }, 100);
    }
  }, []);

  return (
    <div className="dashboard-app-container">
      <Sidebar userRole={user?.role} />
      <main className="dashboard-main">
        <Navbar user={user} logout={handleLogout} />
        <div className="dashboard-content-scroll">
          {children}
        </div>
      </main>
      {isBlocked && <AccessBlocked />}
      
      {/* Bouton toggle sidebar pour mobile */}
      <button 
        className="sidebar-toggle-mobile"
        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
        style={{
          position: 'fixed',
          bottom: '20px',
          right: '20px',
          width: '50px',
          height: '50px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, var(--atj-gold), var(--atj-red))',
          border: 'none',
          color: 'white',
          fontSize: '24px',
          cursor: 'pointer',
          display: 'none',
          boxShadow: 'var(--shadow-lg)',
          zIndex: 1000,
          transition: 'transform 0.3s ease'
        }}
        onMouseEnter={(e) => e.currentTarget.style.transform = 'scale(1.1)'}
        onMouseLeave={(e) => e.currentTarget.style.transform = 'scale(1)'}
      >
        ☰
      </button>
      
      <style>{`
        @media (max-width: 1024px) {
          .sidebar-toggle-mobile {
            display: flex !important;
            align-items: center;
            justify-content: center;
          }
        }
      `}</style>
    </div>
  );
}