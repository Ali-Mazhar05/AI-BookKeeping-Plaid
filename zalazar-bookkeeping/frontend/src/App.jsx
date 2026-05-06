import React from 'react';
import { Routes, Route, NavLink, useLocation } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import ReviewQueue from './components/ReviewQueue';
import TransactionSection from './components/TransactionSection';
import ReconciliationHub from './components/ReconciliationHub';
import { LayoutDashboard, ListChecks, Building2, User, History, ShieldCheck } from 'lucide-react';
import ErrorBoundary from './components/ErrorBoundary';
import './App.css';

function App() {
  const entityId = "665c4049-085d-4f32-b2c7-22bd89668e20"; // Zalazar Holdings
  const location = useLocation();

  const getPageTitle = () => {
    switch (location.pathname) {
      case '/': return 'Portfolio Overview';
      case '/review': return 'Review Queue';
      case '/transactions': return 'Transaction Ledger';
      case '/reconciliation': return 'Reconciliation Hub';
      default: return 'Zalazar Bookkeeping';
    }
  };

  return (
    <div className="app-layout">
      {/* Sidebar / Navigation */}
      <nav className="side-nav">
        <div className="nav-brand">
          <Building2 color="var(--primary-gold)" size={32} />
          <div className="brand-text">
            <span className="brand-name">ZALAZAR</span>
            <span className="brand-sub">BOOKKEEPING</span>
          </div>
        </div>
        
        <div className="nav-links">
          <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <LayoutDashboard size={20} />
            <span>DASHBOARD</span>
          </NavLink>
          
          <NavLink to="/review" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <ListChecks size={20} />
            <span>REVIEW QUEUE</span>
          </NavLink>
          
          <NavLink to="/transactions" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <History size={20} />
            <span>TRANSACTIONS</span>
          </NavLink>

          <NavLink to="/reconciliation" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <ShieldCheck size={20} />
            <span>RECONCILIATION</span>
          </NavLink>
        </div>

        <div className="nav-footer">
          <div className="user-profile">
            <User size={20} />
            <span>JUAN ZALAZAR</span>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="main-content">
        <header className="content-header">
          <h1>{getPageTitle()}</h1>
          <div className="header-actions">
            <span className="entity-label">ENTITY: ZALAZAR HOLDINGS</span>
          </div>
        </header>

        <div className="content-body">
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Dashboard entityId={entityId} />} />
              <Route path="/review" element={<ReviewQueue entityId={entityId} />} />
              <Route path="/transactions" element={<TransactionSection entityId={entityId} />} />
              <Route path="/reconciliation" element={<ReconciliationHub entityId={entityId} />} />
            </Routes>
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}

export default App;
