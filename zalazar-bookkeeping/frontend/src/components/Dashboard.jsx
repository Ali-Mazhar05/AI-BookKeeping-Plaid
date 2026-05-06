import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useNotification } from './Notification';
import {
  AlertCircle, CheckCircle2, TrendingUp, ArrowUpRight,
  ArrowDownRight, Plus, Upload, Building2, PieChart,
  ClipboardList, CheckSquare, XCircle, MoreVertical,
  CreditCard
} from 'lucide-react';
import ManualAccountModal from './ManualAccountModal';
import StatementUploadModal from './StatementUploadModal';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const Dashboard = ({ entityId, entityName }) => {
  const navigate = useNavigate();
  const { showNotification } = useNotification();
  const [stats, setStats] = useState({ pending: 0, reviewed: 0 });
  const [bankAccounts, setBankAccounts] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showManualModal, setShowManualModal] = useState(false);
  const [uploadAccount, setUploadAccount] = useState(null);
  const [selectedMonth, setSelectedMonth] = useState('overall');
  const [availableMonths, setAvailableMonths] = useState([]);
  const [showAiReasoning, setShowAiReasoning] = useState(true);

  useEffect(() => {
    if (entityId) {
      fetchAllData();
    }
  }, [entityId, selectedMonth]);

  const fetchAllData = async () => {
    setLoading(true);
    try {
      await Promise.all([
        fetchStats(),
        fetchBankAccounts(),
        fetchTransactions(),
        fetchReports(),
        fetchAvailableMonths()
      ]);
    } catch (err) {
      console.error("Error fetching dashboard data", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    const response = await axios.get(`${API_BASE}/queue/stats?entity_id=${entityId}`);
    setStats({
      pending: response.data.pending_count,
      reviewed: response.data.reviewed_today
    });
  };

  const fetchBankAccounts = async () => {
    const response = await axios.get(`${API_BASE}/bank-accounts?entity_id=${entityId}`);
    setBankAccounts(response.data.data);
  };

  const fetchTransactions = async () => {
    const response = await axios.get(`${API_BASE}/transactions/?entity_id=${entityId}`);
    setTransactions(response.data.data);
  };

  const fetchReports = async () => {
    let startDate, endDate;

    if (selectedMonth === 'overall') {
      startDate = '2024-01-01';
      endDate = '2026-12-31';
    } else {
      const [year, month] = selectedMonth.split('-');
      startDate = `${year}-${month}-01`;
      endDate = new Date(year, month, 0).toISOString().split('T')[0];
    }

    const response = await axios.get(`${API_BASE}/reports/summary?entity_id=${entityId}&start_date=${startDate}&end_date=${endDate}`);
    setReports(response.data.properties);
  };

  const fetchAvailableMonths = async () => {
    const response = await axios.get(`${API_BASE}/meta/months?entity_id=${entityId}`);
    setAvailableMonths(response.data.data);

    // Auto-select latest month if currently on 'overall' and months exist
    if (selectedMonth === 'overall' && response.data.data.length > 0 && availableMonths.length === 0) {
      setSelectedMonth(response.data.data[0].value);
    }
  };

  const handleApprove = async (txId) => {
    try {
      await axios.post(`${API_BASE}/queue/${txId}/approve`);
      fetchAllData();
    } catch (err) {
      const status = err.response?.status ? `[${err.response.status}]` : '';
      const detail = err.response?.data?.detail || err.message;
      showNotification(`Failed to approve transaction ${status}: ${detail}`, "error");
    }
  };

  const handleRemoveAccount = async (accountId) => {
    if (!window.confirm("Are you sure you want to remove this bank account? This will hide it from the dashboard.")) return;
    try {
      await axios.delete(`${API_BASE}/bank-accounts/${accountId}`);
      fetchBankAccounts();
    } catch (err) {
      const status = err.response?.status ? `[${err.response.status}]` : '';
      const detail = err.response?.data?.detail || err.message;
      showNotification(`Failed to remove bank account ${status}: ${detail}`, "error");
    }
  };

  const totalCash = bankAccounts.reduce((sum, acc) => sum + (parseFloat(acc.current_balance) || 0), 0);

  if (loading && transactions.length === 0) return <div className="premium-card">Loading Enterprise Data...</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-xl)', width: '100%' }}>

      {/* Header Section */}
      <div style={{ borderBottom: '1px solid var(--border-light)', paddingBottom: '14px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ minWidth: 0 }}>
            <label style={{ fontSize: '11px', letterSpacing: '0.12em', color: 'var(--primary-gold)' }}>BOOKKEEPING OVERVIEW</label>
            <h1 style={{ fontSize: '28px', marginTop: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{entityName || 'Zalazar Holdings'}</h1>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
            <select
              className="form-select"
              style={{ fontSize: '12px', height: '40px', minWidth: '150px' }}
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
            >
              {availableMonths.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
              <option value="overall">Overall Total</option>
            </select>
            <button
              className="btn-secondary"
              onClick={() => setShowAiReasoning(!showAiReasoning)}
              style={{
                background: showAiReasoning ? 'rgba(193, 155, 46, 0.1)' : 'transparent',
                borderColor: showAiReasoning ? 'var(--primary-gold)' : 'var(--border-light)',
                padding: '8px 12px',
                fontSize: '11px',
                height: '38px'
              }}
            >
              {showAiReasoning ? 'Hide AI' : 'Show AI'}
            </button>
            <button className="btn-secondary" onClick={fetchAllData} title="Refresh" style={{ padding: '8px 12px', fontSize: '11px', height: '38px' }}>
              <Plus size={14} style={{ transform: 'rotate(45deg)' }} />
            </button>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn-secondary" style={{ flex: 1, fontSize: '12px', padding: '8px', height: '36px', justifyContent: 'center', display: 'flex', alignItems: 'center', gap: '6px' }} onClick={() => setUploadAccount({ id: null, bank_name: 'Auto-Identify', account_name: 'Statement' })}>
            <Upload size={14} /> Upload Statement
          </button>
          <button className="btn-secondary" style={{ flex: 1, fontSize: '12px', padding: '8px', height: '36px', justifyContent: 'center', display: 'flex', alignItems: 'center', gap: '6px' }} onClick={() => setShowManualModal(true)}>
            <Plus size={14} /> Add Account
          </button>
        </div>
      </div>

      {/* Top Stats Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
        {[
          { label: 'Total Cash', icon: <TrendingUp color="var(--primary-gold)" size={18} />, value: `$${totalCash.toLocaleString(undefined, { minimumFractionDigits: 2 })}`, accent: false },
          { label: 'Queue Status', icon: <ClipboardList color="var(--primary-gold)" size={18} />, value: `${stats.pending} Pending`, accent: true, valueColor: stats.pending > 0 ? '#ba1a1a' : 'inherit' },
          { label: 'Properties', icon: <Building2 color="var(--primary-gold)" size={18} />, value: reports.length, accent: false },
        ].map((card, i) => (
          <div key={i} className="premium-card" style={{ borderLeft: card.accent ? '4px solid var(--primary-gold)' : undefined, padding: '14px', display: 'flex', flexDirection: 'column', gap: '8px', minWidth: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={{ margin: 0, fontSize: '10px' }}>{card.label}</label>
              {card.icon}
            </div>
            <div style={{ fontSize: 'clamp(18px, 4vw, 28px)', fontWeight: 600, fontFamily: 'var(--font-headline)', color: card.valueColor, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {card.value}
            </div>
          </div>
        ))}
      </div>

      {/* Property Performance Section */}
      <section>
        <h2 style={{ fontSize: '20px', marginBottom: 'var(--spacing-lg)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <PieChart size={20} /> Property Performance ({selectedMonth === 'overall' ? 'All Time' : selectedMonth})
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 320px), 1fr))', gap: '12px' }}>
          {reports.map(report => (
            <div 
              key={report.property_id} 
              className="premium-card" 
              style={{ padding: 0, overflow: 'hidden', cursor: 'pointer' }}
              onClick={() => navigate(`/transactions?property_id=${report.property_id}`)}
            >
              <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                <h4 style={{ margin: 0, fontSize: '15px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{report.property_name}</h4>
                <div style={{
                  padding: '3px 10px',
                  borderRadius: '10px',
                  fontSize: '11px',
                  fontWeight: 700,
                  flexShrink: 0,
                  background: report.dscr >= 1.25 ? '#e6f4ea' : '#fce8e6',
                  color: report.dscr >= 1.25 ? '#1e7e34' : '#c5221f'
                }}>
                  DSCR: {report.dscr.toFixed(2)}
                </div>
              </div>
              <div style={{ padding: '14px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '9px', color: 'var(--text-muted)', margin: 0 }}>NET OPERATING INCOME</label>
                  <div style={{ fontWeight: 700, fontSize: '14px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>${report.metrics.noi.toLocaleString()}</div>
                </div>
                <div>
                  <label style={{ fontSize: '9px', color: 'var(--text-muted)', margin: 0 }}>DEBT SERVICE</label>
                  <div style={{ fontWeight: 700, fontSize: '14px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>${report.metrics.total_debt_service.toLocaleString()}</div>
                </div>
                <div style={{ gridColumn: '1 / -1' }}>
                  <div style={{ height: '4px', background: 'var(--border-light)', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%',
                      background: 'var(--primary-gold)',
                      width: `${Math.min(100, (report.metrics.noi / (report.metrics.total_debt_service || 1)) * 100)}%`
                    }}></div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Main Grid: Accounts & Queue */}
      <div className="dashboard-main-grid">

        {/* Bank Accounts */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
          <h2 style={{ fontSize: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CreditCard size={20} /> Bank Accounts
          </h2>
          <div className="premium-card" style={{ padding: 0 }}>
            {bankAccounts.length === 0 ? (
              <div style={{ padding: 'var(--spacing-lg)', textAlign: 'center', color: 'var(--text-muted)' }}>No accounts connected.</div>
            ) : (
              bankAccounts.map(acc => (
                <div key={acc.id} className="account-compact-row">
                  <div style={{ overflow: 'hidden' }}>
                    <div style={{ fontWeight: 800, fontSize: '13px', letterSpacing: '0.02em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{acc.bank_name.toUpperCase()}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>****{acc.account_last4}</div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      className="btn-secondary"
                      style={{ padding: '6px 10px', fontSize: '10px', border: 'none', background: '#f0f0f0' }}
                      onClick={() => setUploadAccount(acc)}
                      title="Upload Statement"
                    >
                      <Upload size={14} />
                    </button>
                    <button
                      className="btn-secondary"
                      style={{ padding: '6px 10px', fontSize: '10px', border: 'none', background: 'rgba(186, 26, 26, 0.05)', color: '#ba1a1a' }}
                      onClick={() => handleRemoveAccount(acc.id)}
                      title="Remove Account"
                    >
                      <XCircle size={14} />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        {/* Transaction Queue */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)', width: '100%' }}>
          <h2 style={{ fontSize: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckSquare size={20} /> Transactions
          </h2>
          <div className="premium-card desktop-table-only" style={{ padding: 0, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', minWidth: '700px' }}>
              <thead>
                <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border-light)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '12px var(--spacing-lg)' }}>DATE</th>
                  <th style={{ padding: '12px var(--spacing-lg)' }}>DESCRIPTION & AI REASONING</th>
                  <th style={{ padding: '12px var(--spacing-lg)' }}>AMOUNT</th>
                  <th className="hide-mobile" style={{ padding: '12px var(--spacing-lg)' }}>STATUS</th>
                  <th style={{ padding: '12px var(--spacing-lg)' }}></th>
                </tr>
              </thead>
              <tbody>
                {transactions.length === 0 ? (
                  <tr><td colSpan="5" style={{ textAlign: 'center', padding: '40px' }}>No transactions found.</td></tr>
                ) : (
                  transactions.slice(0, 8).map(tx => (
                    <tr key={tx.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                      <td style={{ padding: '12px var(--spacing-lg)' }}>{new Date(tx.transaction_date).toLocaleDateString()}</td>
                      <td style={{ padding: '12px var(--spacing-lg)' }}>
                        <div style={{ fontWeight: 600 }}>{tx.vendor_name_clean}</div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', maxWidth: '300px' }}>
                          {tx.status === 'ai_suggested' && tx.categorization_reason && showAiReasoning ? (
                            <div style={{ fontStyle: 'italic', color: 'var(--primary-gold)', marginTop: '4px' }}>
                              AI: {tx.categorization_reason.split(' ').slice(0, 10).join(' ')}{tx.categorization_reason.split(' ').length > 10 ? '...' : ''}
                            </div>
                          ) : tx.description_clean}
                        </div>
                      </td>
                      <td style={{ padding: '12px var(--spacing-lg)', fontWeight: 700, color: tx.amount < 0 ? 'inherit' : '#1e7e34' }}>
                        ${Math.abs(tx.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="hide-mobile" style={{ padding: '12px var(--spacing-lg)' }}>
                        <span style={{
                          fontSize: '10px',
                          fontWeight: 800,
                          padding: '3px 10px',
                          borderRadius: '0',
                          background: tx.status === 'ai_suggested' ? 'var(--primary-gold)' : '#111',
                          color: '#fff',
                          textTransform: 'uppercase',
                          letterSpacing: '0.05em'
                        }}>
                          {tx.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td style={{ padding: '12px var(--spacing-lg)', textAlign: 'right' }}>
                        {tx.status === 'ai_suggested' && (
                          <button
                            onClick={() => handleApprove(tx.id)}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary-gold)' }}
                            title="Approve AI Suggestion"
                          >
                            <CheckCircle2 size={18} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            {transactions.length > 8 && (
              <div style={{ padding: '12px', textAlign: 'center', borderTop: '1px solid var(--border-light)' }}>
                <button className="btn-secondary" onClick={() => navigate('/transactions')} style={{ fontSize: '11px' }}>View All Transactions</button>
              </div>
            )}
          </div>

          {/* Mobile card preview */}
          <div className="mobile-card-list premium-card" style={{ padding: 0 }}>
            {transactions.slice(0, 8).map(tx => (
              <div key={tx.id} style={{ padding: '10px 14px', borderBottom: '1px solid var(--border-light)' }}>
                {/* Date + Amount row */}
                <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {new Date(tx.transaction_date).toLocaleDateString()}
                  </span>
                  <span style={{ fontWeight: 800, fontSize: '14px', whiteSpace: 'nowrap', color: tx.amount < 0 ? '#ba1a1a' : '#1e7e34' }}>
                    {tx.amount < 0 ? '-' : '+'}${Math.abs(tx.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
                {/* Vendor name */}
                <div style={{ fontWeight: 700, fontSize: '12px', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: '4px' }}>
                  {tx.vendor_name_clean || 'Direct Entry'}
                </div>
                {/* Status + approve button */}
                <div style={{ display: 'grid', gridTemplateColumns: tx.status === 'ai_suggested' ? 'minmax(0, 1fr) auto' : '1fr', alignItems: 'center', gap: '8px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, padding: '2px 8px', background: tx.status === 'ai_suggested' ? 'var(--primary-gold)' : '#111', color: '#fff', textTransform: 'uppercase', letterSpacing: '0.04em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {tx.status.replace(/_/g, ' ')}
                  </div>
                  {tx.status === 'ai_suggested' && (
                    <button onClick={() => handleApprove(tx.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary-gold)', padding: '2px', display: 'flex', justifyContent: 'center' }} title="Approve">
                      <CheckCircle2 size={16} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      {showManualModal && (
        <ManualAccountModal
          entityId={entityId}
          onClose={() => setShowManualModal(false)}
          onSuccess={fetchAllData}
        />
      )}

      {uploadAccount && (
        <StatementUploadModal
          account={uploadAccount}
          onClose={() => setUploadAccount(null)}
          onSuccess={fetchAllData}
        />
      )}
    </div>

  );
};

export default Dashboard;
