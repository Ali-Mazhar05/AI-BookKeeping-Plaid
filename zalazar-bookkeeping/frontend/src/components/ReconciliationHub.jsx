import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import { ShieldCheck, AlertTriangle, CheckCircle, Clock, ChevronRight, RefreshCcw, ExternalLink } from 'lucide-react';
import { useNotification } from './Notification';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const ReconciliationHub = ({ entityId }) => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchParams] = useSearchParams();
  const highlightedId = searchParams.get('id');
  const [triggering, setTriggering] = useState(false);
  const { showNotification } = useNotification();

  useEffect(() => {
    if (entityId) {
      fetchLogs();
    }
  }, [entityId]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE}/reconciliation/logs?entity_id=${entityId}`);
      setLogs(response.data);
    } catch (err) {
      console.error("Error fetching reconciliation logs", err);
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerRecon = async (accountId) => {
    setTriggering(true);
    try {
      await axios.post(`${API_BASE}/reconciliation/trigger/${accountId}`);
      showNotification("Reconciliation triggered. Please refresh in a few moments.", "success");
      fetchLogs();
    } catch (err) {
      const status = err.response?.status ? `[${err.response.status}]` : '';
      const detail = err.response?.data?.detail || err.message;
      showNotification(`Failed to trigger reconciliation ${status}: ${detail}`, "error");
    } finally {
      setTriggering(false);
    }
  };

  return (
    <div className="reconciliation-hub">
      <div className="premium-card">
        <div className="mobile-flex-col" style={{ padding: 'var(--spacing-lg)', borderBottom: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--spacing-md)' }}>
          <div>
            <h2 style={{ fontSize: '24px', margin: 0 }}>Reconciliation Hub</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Daily automated balancing between Bank (Plaid) and Ledger.</p>
          </div>
          <button className="btn-secondary mobile-full-width" onClick={fetchLogs} disabled={loading}>
            <RefreshCcw size={16} className={loading ? 'spin' : ''} /> <span className="show-mobile-only" style={{ marginLeft: '8px' }}>REFRESH</span>
          </button>
        </div>

        <div style={{ padding: 'var(--spacing-lg)' }}>
          {loading && logs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px' }}>Loading audit logs...</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
              {logs.map(log => (
                <div 
                  key={log.id} 
                  className={`recon-item ${highlightedId === String(log.id) ? 'highlighted-item' : ''}`}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    padding: 'var(--spacing-lg)',
                    borderRadius: '16px',
                    background: 'rgba(255, 255, 255, 0.03)',
                    border: '1px solid var(--border-light)',
                    transition: 'all 0.3s ease'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', marginBottom: 'var(--spacing-lg)' }}>
                    <div style={{ 
                      width: '40px', 
                      height: '40px', 
                      borderRadius: '10px', 
                      background: log.status === 'matched' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      marginRight: 'var(--spacing-md)'
                    }}>
                      {log.status === 'matched' ? (
                        <CheckCircle size={20} color="#22c55e" />
                      ) : (
                        <AlertTriangle size={20} color="#ef4444" />
                      )}
                    </div>

                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, fontSize: '16px' }}>{log.account_name}</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        Date: {log.reconciliation_date} • {log.status.toUpperCase()}
                      </div>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Variance</div>
                      <div style={{ fontWeight: 800, fontSize: '20px', color: log.difference === 0 ? 'var(--text-main)' : '#ef4444' }}>
                        ${Math.abs(log.difference).toFixed(2)}
                      </div>
                    </div>
                  </div>

                  <div className="mobile-grid-1" style={{ 
                    display: 'grid', 
                    gridTemplateColumns: '1fr 1fr', 
                    gap: '12px', 
                    background: 'rgba(0,0,0,0.05)', 
                    padding: '12px', 
                    borderRadius: '8px',
                    fontSize: '13px'
                  }}>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Plaid Balance:</span>
                      <span style={{ marginLeft: '8px', fontWeight: 600 }}>${log.plaid_balance.toLocaleString()}</span>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Ledger Balance:</span>
                      <span style={{ marginLeft: '8px', fontWeight: 600 }}>${log.calculated_balance.toLocaleString()}</span>
                    </div>
                  </div>

                  {log.status !== 'matched' && (
                    <div className="mobile-flex-col" style={{ marginTop: '16px', display: 'flex', gap: '12px' }}>
                      <button 
                        className="btn-primary" 
                        style={{ fontSize: '12px', padding: '12px 16px', background: 'var(--primary-gold)', color: '#000', flex: 1 }}
                        onClick={() => handleTriggerRecon(log.bank_account_id)}
                        disabled={triggering}
                      >
                        {triggering ? 'RE-RUNNING...' : 'RE-RUN RECONCILIATION'}
                      </button>
                      <button 
                        className="btn-secondary" 
                        style={{ fontSize: '12px', padding: '12px 16px', flex: 1 }}
                        onClick={() => window.location.href = '/review'}
                      >
                        CHECK REVIEW QUEUE
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {logs.length === 0 && !loading && (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  No reconciliation history found for this entity.
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <style>{`
        .highlighted-item {
          border: 2px solid var(--primary-gold) !important;
          background: rgba(212, 175, 55, 0.08) !important;
          transform: scale(1.01);
          box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }
        .spin {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default ReconciliationHub;
