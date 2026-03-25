import React, { useState, useEffect, useContext } from "react";
import API from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import DashboardLayout from "./DashboardLayout";
import "./AdminDashboard.css";

export default function AdminDashboard() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const { user } = useContext(AuthContext);

  const [showModal, setShowModal] = useState(false);
  const [newUser, setNewUser] = useState({ email: "", password: "", role: "employer" });
  const [passwordModal, setPasswordModal] = useState({ show: false, userId: null });
  const [passwordData, setPasswordData] = useState({ newPassword: "", confirmPassword: "" });

  const authHeader = { headers: { Authorization: `Bearer ${user?.token}` } };

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const res = await API.get("/users", authHeader);
      setUsers(res.data);
    } catch (err) {
      console.error("Erreur :", err);
      alert("Erreur lors du chargement des utilisateurs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (user) fetchUsers(); }, [user]);

  const handleAction = async (method, url, data = {}) => {
    try {
      await API[method](url, data, authHeader);
      fetchUsers();
    } catch (err) {
      alert(err.response?.data?.detail || "Action impossible.");
    }
  };

  const handlePasswordChange = async () => {
    if (passwordData.newPassword !== passwordData.confirmPassword) return alert("Incohérence mots de passe.");
    await handleAction('put', `/users/${passwordModal.userId}/password`, { password: passwordData.newPassword });
    setPasswordModal({ show: false, userId: null });
  };

  const handleCreateUser = async () => {
    await handleAction('post', "/users", newUser);
    setShowModal(false);
    setNewUser({ email: "", password: "", role: "employer" });
  };

  return (
    <DashboardLayout user={user}>
      <div className="admin-view-header">
        <div className="header-text">
          <h2>Gestion des Utilisateurs</h2>
          <p>Administration du portail Attijari Bank</p>
        </div>
        <div className="header-action-btns">
          <button className="btn-header btn-refresh" onClick={fetchUsers}>
            <span>🔄</span> Actualiser
          </button>
          <button className="btn-header btn-add" onClick={() => setShowModal(true)}>
            <span>👤+</span> Créer un utilisateur
          </button>
        </div>
      </div>

      <div className="table-container-glass">
        <table className="attijari-table-modern">
          <thead>
            <tr>
              <th>UTILISATEUR</th>
              <th>RÔLE</th>
              <th>STATUT</th>
              <th className="text-center">ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="4" className="loading-state">Chargement...</td></tr>
            ) : users.map(u => (
              <tr key={u.id}>
                <td className="email-cell">
                  <div className="user-info-flex">
                    <div className="user-avatar-small">{u.email.charAt(0).toUpperCase()}</div>
                    <span>{u.email}</span>
                  </div>
                </td>
                <td>
                  <span className={`role-tag ${u.role}`}>{u.role}</span>
                </td>
                <td>
                  <span className={`status-dot-pill ${u.is_active ? "active" : "pending"}`}>
                    {u.is_active ? "Actif" : "En attente"}
                  </span>
                </td>
                <td>
                  <div className="horizontal-action-wrapper">
                    {!u.is_active ? (
                      <button className="icon-action-btn approve" title="Approuver" onClick={() => handleAction('put', `/users/${u.id}/activate`)}>Approuver</button>
                    ) : (
                      <button className="icon-action-btn deactivate" title="Désactiver" onClick={() => handleAction('put', `/users/${u.id}/deactivate`)}>Désactiver</button>
                    )}
                    <button className="icon-action-btn role" title="Rôle" onClick={() => handleAction('put', `/users/${u.id}`, { role: u.role === 'admin' ? 'employer' : 'admin' })}>Rôle</button>
                    <button className="icon-action-btn pwd" title="Password" onClick={() => setPasswordModal({ show: true, userId: u.id })}>🔒</button>
                    <button className="icon-action-btn delete" title="Supprimer" onClick={() => { if(window.confirm("Supprimer ?")) handleAction('delete', `/users/${u.id}`) }}>🗑️</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modale Password */}
      {passwordModal.show && (
        <div className="modal-overlay" onClick={() => setPasswordModal({ show: false, userId: null })}>
          <div className="modal-glass-card" onClick={e => e.stopPropagation()}>
            <h3>🔒 Sécurité Compte</h3>
            <p>Définir un nouveau mot de passe pour cet utilisateur.</p>
            <input type="password" placeholder="Nouveau mot de passe" onChange={e => setPasswordData({...passwordData, newPassword: e.target.value})} />
            <input type="password" placeholder="Confirmer" onChange={e => setPasswordData({...passwordData, confirmPassword: e.target.value})} />
            <div className="modal-actions-row">
              <button className="btn-cancel-glass" onClick={() => setPasswordModal({ show: false })}>Annuler</button>
              <button className="btn-confirm-glass" onClick={handlePasswordChange}>Enregistrer</button>
            </div>
          </div>
        </div>
      )}

      {/* Modale Création */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-glass-card" onClick={e => e.stopPropagation()}>
            <h3>👤 Nouvel Utilisateur</h3>
            <input type="email" placeholder="Email Esprit ou Banque" value={newUser.email} onChange={e => setNewUser({...newUser, email: e.target.value})} />
            <input type="password" placeholder="Mot de passe provisoire" value={newUser.password} onChange={e => setNewUser({...newUser, password: e.target.value})} />
            <select value={newUser.role} onChange={e => setNewUser({...newUser, role: e.target.value})}>
              <option value="employer">Employer</option>
              <option value="admin">Admin</option>
            </select>
            <div className="modal-actions-row">
              <button className="btn-cancel-glass" onClick={() => setShowModal(false)}>Annuler</button>
              <button className="btn-confirm-glass" onClick={handleCreateUser}>Créer le compte</button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}