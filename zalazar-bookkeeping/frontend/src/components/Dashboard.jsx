import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useNotification } from './Notification';
import {
  AlertCircle, CheckCircle2, TrendingUp, ArrowUpRight,
  ArrowDownRight, Plus, Upload, Building2, PieChart,
  ClipboardList, CheckSquare, XCircle, X, MoreVertical,
  CreditCard, Tag
} from 'lucide-react';
import AddAccountModal from './AddAccountModal';
import AddPropertyModal from './AddPropertyModal';
import StatementUploadModal from './StatementUploadModal';
import PlaidLinkButton from './PlaidLinkButton';
import ConfirmModal from './ConfirmModal';
import ManageCategoriesModal from './ManageCategoriesModal';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const Dashboard = ({ entityId, entityName }) => {
  const navigate = useNavigate();
  const { showNotification } = useNotification();
  const [stats, setStats] = useState({ pending: 0, reviewed: 0 });
  const [bankAccounts, setBankAccounts] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddAccountModal, setShowAddAccountModal] = useState(false);
  const [showAddPropertyModal, setShowAddPropertyModal] = useState(false);
  const [showManageCategoriesModal, setShowManageCategoriesModal] = useState(false);
  const [uploadAccount, setUploadAccount] = useState(null);
  const [selectedMonth, setSelectedMonth] = useState('overall');
  const [availableMonths, setAvailableMonths] = useState([]);
  const [showAiReasoning, setShowAiReasoning] = useState(true);

  // Confirm dialog state
  const [confirm, setConfirm] = useState({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: null,
    danger: false,
    warning: false,
    secondaryAction: null,
  });

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

    if (selectedMonth === 'overall' && response.data.data.length > 0 && availableMonths.length === 0) {
      setSelectedMonth(response.data.data[0].value);
    }
  };

  const closeConfirm = () => setConfirm(prev => ({ ...prev, isOpen: false }));

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

  const handleRemoveAccount = (accountId) => {
    setConfirm({
      isOpen: true,
      title: 'Remove Bank Account',
      message: 'Remove this bank account from the dashboard? The account will be hidden but its transaction history will be preserved.',
      danger: true,
      warning: false,
      secondaryAction: null,
      onConfirm: async () => {
        closeConfirm();
        try {
          await axios.delete(`${API_BASE}/bank-accounts/${accountId}`);
          fetchBankAccounts();
          showNotification('Bank account removed.', 'success');
        } catch (err) {
          const status = err.response?.status ? `[${err.response.status}]` : '';
          const detail = err.response?.data?.detail || err.message;
          showNotification(`Failed to remove bank account ${status}: ${detail}`, "error");
        }
      },
    });
  };

  const handleRemoveProperty = async (propertyId, propertyName) => {
    // Check if any transactions are allocated to this property
    try {
      const res = await axios.get(`${API_BASE}/meta/properties/${propertyId}/tx-count`);
      const count = res.data.count;

      if (count > 0) {
        setConfirm({
          isOpen: true,
          title: 'Property Has Transactions',
          message: `"${propertyName}" is linked to ${count} transaction allocation${count !== 1 ? 's' : ''}. Reassign those transactions to a different property before removing this one.`,
          danger: false,
          warning: true,
          secondaryAction: {
            label: `View ${count} Transaction${count !== 1 ? 's' : ''}`,
            onClick: () => {
              closeConfirm();
              navigate(`/transactions?property_id=${propertyId}`);
            },
          },
          onConfirm: closeConfirm,
        });
        return;
      }

      // Safe to remove
      setConfirm({
        isOpen: true,
        title: 'Remove Property',
        message: `Remove "${propertyName}" from the dashboard? The property will be hidden but can be restored at any time from the Add Property menu.`,
        danger: true,
        warning: false,
        secondaryAction: null,
        onConfirm: async () => {
          closeConfirm();
          try {
            await axios.delete(`${API_BASE}/meta/properties/${propertyId}`);
            fetchReports();
            showNotification(`"${propertyName}" removed from dashboard.`, 'success');
          } catch (err) {
            const status = err.response?.status ? `[${err.response.status}]` : '';
            const detail = err.response?.data?.detail || err.message;
            showNotification(`Failed to remove property ${status}: ${detail}`, "error");
          }
        },
      });
    } catch {
      showNotification('Failed to check property usage.', 'error');
    }
  };

  const totalCash = bankAccounts.reduce((sum, acc) => sum + (parseFloat(acc.current_balance) || 0), 0);

  const formatRelativeTime = (iso) => {
    const diff = Date.now() - new Date(iso).getTime();
    const h = Math.floor(diff / 3600000);
    const m = Math.floor(diff / 60000);
    if (h > 48) return `${Math.floor(h / 24)}d ago`;
    if (h > 0)  return `${h}h ago`;
    return `${m}m ago`;
  };

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
          <button className="btn-secondary" style={{ flex: 1, fontSize: '12px', padding: '8px', height: '36px', justifyContent: 'center', display: 'flex', alignItems: 'center', gap: '6px' }} onClick={() => setShowAddAccountModal(true)}>
            <Plus size={14} /> Add Account
          </button>
          <button className="btn-secondary" style={{ flex: 1, fontSize: '12px', padding: '8px', height: '36px', justifyContent: 'center', display: 'flex', alignItems: 'center', gap: '6px' }} onClick={() => setShowManageCategoriesModal(true)}>
            <Tag size={14} /> Categories
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-lg)' }}>
          <h2 style={{ fontSize: '20px', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
            <PieChart size={20} /> Property Performance ({selectedMonth === 'overall' ? 'All Time' : selectedMonth})
          </h2>
          <button
            className="btn-primary"
            style={{ fontSize: '11px', padding: '6px 12px', height: '32px', display: 'flex', alignItems: 'center', gap: '6px' }}
            onClick={() => setShowAddPropertyModal(true)}
          >
            <Plus size={13} /> Add Property
          </button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 320px), 1fr))', gap: '12px' }}>
          {reports.map(report => (
            <div
              key={report.property_id}
              className="premium-card"
              style={{ padding: 0, overflow: 'hidden' }}
            >
              <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                <h4
                  style={{ margin: 0, fontSize: '15px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, cursor: 'pointer' }}
                  onClick={() => navigate(`/transactions?property_id=${report.property_id}`)}
                >
                  {report.property_name}
                </h4>
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
                <button
                  onClick={() => handleRemoveProperty(report.property_id, report.property_name)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px', lineHeight: 0, color: 'var(--text-muted)', flexShrink: 0 }}
                  title="Remove property"
                >
                  <X size={14} />
                </button>
              </div>
              <div
                style={{ padding: '14px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', cursor: 'pointer' }}
                onClick={() => navigate(`/transactions?property_id=${report.property_id}`)}
              >
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
          {reports.length === 0 && (
            <div className="premium-card" style={{ padding: '32px', textAlign: 'center', gridColumn: '1 / -1' }}>
              <div style={{ color: 'var(--text-muted)', fontSize: '13px', marginBottom: '16px' }}>No properties configured yet.</div>
              <button className="btn-primary" style={{ fontSize: '12px', padding: '8px 20px', display: 'inline-flex', alignItems: 'center', gap: '6px' }} onClick={() => setShowAddPropertyModal(true)}>
                <Plus size={14} /> Add Your First Property
              </button>
            </div>
          )}
        </div>
      </section>

      {/* Main Grid: Accounts & Queue */}
      <div className="dashboard-main-grid">

        {/* Bank Accounts */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: '20px', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
              <CreditCard size={20} /> Bank Accounts
            </h2>
            <button
              className="btn-primary"
              style={{ fontSize: '11px', padding: '6px 12px', height: '32px', display: 'flex', alignItems: 'center', gap: '6px' }}
              onClick={() => setShowAddAccountModal(true)}
            >
              <Plus size={13} /> Add Account
            </button>
          </div>

          <div className="premium-card" style={{ padding: 0 }}>
            {bankAccounts.length === 0 ? (
              <div style={{ padding: '32px', textAlign: 'center' }}>
                <div style={{ color: 'var(--text-muted)', fontSize: '13px', marginBottom: '16px' }}>No accounts connected yet.</div>
                <button className="btn-primary" style={{ fontSize: '12px', padding: '8px 20px', display: 'inline-flex', alignItems: 'center', gap: '6px' }} onClick={() => setShowAddAccountModal(true)}>
                  <Plus size={14} /> Connect Your First Bank
                </button>
              </div>
            ) : (
              bankAccounts.map((acc, i) => (
                <div key={acc.id} style={{
                  padding: '14px 16px',
                  borderBottom: i < bankAccounts.length - 1 ? '1px solid var(--border-light)' : 'none',
                  display: 'flex', flexDirection: 'column', gap: '8px',
                }}>
                  {/* Row 1: Name + badge + balance */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                      <span style={{ fontWeight: 800, fontSize: '13px', letterSpacing: '0.02em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {acc.bank_name.toUpperCase()}
                      </span>
                      <span style={{
                        fontSize: '9px', fontWeight: 800, padding: '2px 7px', letterSpacing: '0.08em',
                        borderRadius: '2px', flexShrink: 0,
                        background: acc.source_type === 'plaid' ? 'rgba(193,155,46,0.12)' : 'rgba(0,0,0,0.06)',
                        color: acc.source_type === 'plaid' ? 'var(--primary-gold)' : 'var(--text-muted)',
                      }}>
                        {acc.source_type === 'plaid' ? 'PLAID' : 'MANUAL'}
                      </span>
                    </div>
                    <span style={{ fontWeight: 700, fontSize: '15px', whiteSpace: 'nowrap' }}>
                      {acc.current_balance != null
                        ? `$${parseFloat(acc.current_balance).toLocaleString(undefined, { minimumFractionDigits: 2 })}`
                        : '—'}
                    </span>
                  </div>

                  {/* Row 2: Account detail + last synced + actions */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                    <div style={{ minWidth: 0 }}>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>
                        {acc.account_name}{acc.account_last4 ? ` ****${acc.account_last4}` : ''}
                      </span>
                      {acc.source_type === 'plaid' && acc.last_synced_at && (
                        <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginLeft: '10px' }}>
                          Synced {formatRelativeTime(acc.last_synced_at)}
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                      <button
                        className="btn-secondary"
                        style={{ padding: '5px 9px', fontSize: '10px', border: 'none', background: '#f0f0f0', lineHeight: 0 }}
                        onClick={() => setUploadAccount(acc)}
                        title="Upload Statement"
                      >
                        <Upload size={13} />
                      </button>
                      <button
                        className="btn-secondary"
                        style={{ padding: '5px 9px', fontSize: '10px', border: 'none', background: 'rgba(186,26,26,0.05)', color: '#ba1a1a', lineHeight: 0 }}
                        onClick={() => handleRemoveAccount(acc.id)}
                        title="Remove Account"
                      >
                        <XCircle size={13} />
                      </button>
                    </div>
                  </div>

                  {/* Row 3: Error / re-link banner */}
                  {acc.plaid_last_error && (
                    <div style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      gap: '10px', padding: '8px 10px',
                      background: 'rgba(186,26,26,0.06)', borderRadius: '4px',
                      border: '1px solid rgba(186,26,26,0.15)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <AlertCircle size={13} color="#ba1a1a" />
                        <span style={{ fontSize: '11px', color: '#ba1a1a', fontWeight: 700 }}>
                          {acc.plaid_last_error.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <PlaidLinkButton
                        entityId={entityId}
                        accountId={acc.plaid_account_id}
                        label="RE-LINK"
                        className="btn-secondary"
                        onLinkSuccess={fetchBankAccounts}
                      />
                    </div>
                  )}
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
                <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {new Date(tx.transaction_date).toLocaleDateString()}
                  </span>
                  <span style={{ fontWeight: 800, fontSize: '14px', whiteSpace: 'nowrap', color: tx.amount < 0 ? '#ba1a1a' : '#1e7e34' }}>
                    {tx.amount < 0 ? '-' : '+'}${Math.abs(tx.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div style={{ fontWeight: 700, fontSize: '12px', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: '4px' }}>
                  {tx.vendor_name_clean || 'Direct Entry'}
                </div>
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

      {/* Modals */}
      {showAddAccountModal && (
        <AddAccountModal
          entityId={entityId}
          onClose={() => setShowAddAccountModal(false)}
          onSuccess={fetchAllData}
        />
      )}

      {showAddPropertyModal && (
        <AddPropertyModal
          entityId={entityId}
          onClose={() => setShowAddPropertyModal(false)}
          onSuccess={fetchReports}
        />
      )}

      {showManageCategoriesModal && (
        <ManageCategoriesModal
          onClose={() => setShowManageCategoriesModal(false)}
          onSuccess={() => {}}
        />
      )}

      {uploadAccount && (
        <StatementUploadModal
          account={uploadAccount}
          onClose={() => setUploadAccount(null)}
          onSuccess={fetchAllData}
        />
      )}

      <ConfirmModal
        isOpen={confirm.isOpen}
        title={confirm.title}
        message={confirm.message}
        confirmText="Remove"
        cancelText="Cancel"
        danger={confirm.danger}
        warning={confirm.warning}
        secondaryAction={confirm.secondaryAction}
        onConfirm={confirm.onConfirm}
        onCancel={closeConfirm}
      />
    </div>
  );
};

export default Dashboard;
