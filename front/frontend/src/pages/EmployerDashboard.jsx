import React, { useContext } from "react";
import { AuthContext } from "../context/AuthContext";
import DashboardLayout from "./DashboardLayout";
import "./AdminDashboard.css"; // tu peux réutiliser le même style

export default function EmployerDashboard() {
  const { user } = useContext(AuthContext);

  return (
    <DashboardLayout user={user}>
      
      {/* Header */}
      <div className="admin-view-header">
        <div className="header-text">
          <h2>Employer Dashboard</h2>
          <p>Bienvenue dans votre espace employeur</p>
        </div>
      </div>


    </DashboardLayout>
  );
}