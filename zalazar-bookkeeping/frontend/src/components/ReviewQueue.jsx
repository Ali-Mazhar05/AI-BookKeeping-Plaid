import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import { Check, X, Edit3, CheckCircle2, Save, Trash2, RefreshCcw, MoreHorizontal, Layers } from 'lucide-react';
import { useNotification } from './Notification';
import ConfirmModal from './ConfirmModal';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const EditModal = ({ transaction, accounts, properties, onSave, onCancel }) => {
  const [accountId, setAccountId] = useState(transaction.account_id || '');
  const [propertyId, setPropertyId] = useState(transaction.property_id || '');
  const [loading, setLoading] = useState(false);

  const handleSave = async () => {
    if (!accountId || !propertyId) {
      showNotification("Please select both an Account and a Property.", "warning");
      return;
    }
    setLoading(true);
    try {
      await onSave(transaction.id, {
        account_id: accountId,
        allocations: [{ property_id: propertyId, amount: transaction.amount }]
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="premium-card modal-content" style={{ maxWidth: '600px', width: '100%', padding: 'var(--spacing-xl)', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--spacing-xl)' }}>
          <div>
            <label>Manual Review</label>
            <h2 style={{ fontSize: '32px', margin: 0 }}>Correct Record</h2>
          </div>
          <button onClick={onCancel} style={{ background: 'none', border: 'none', color: 'var(--text-main)', cursor: 'pointer' }}>
            <X size={24} />
          </button>
        </div>

        <div style={{ marginBottom: 'var(--spacing-xl)', paddingBottom: 'var(--spacing-lg)', borderBottom: '1px solid var(--border-light)' }}>
          <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-headline)' }}>{transaction.vendor_name_clean || transaction.description_raw}</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '14px', fontWeight: 600 }}>
            {transaction.transaction_date} • {transaction.amount < 0 ? `-$${Math.abs(transaction.amount).toFixed(2)}` : `+$${transaction.amount.toFixed(2)}`}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
          <div>
            <label>Chart of Account (Category)</label>
            <select
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="form-select"
            >
              <option value="">Select Category...</option>
              {accounts.map(acc => (
                <option key={acc.id} value={acc.id}>{acc.code} - {acc.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label>Property Attribution</label>
            <select
              value={propertyId}
              onChange={(e) => setPropertyId(e.target.value)}
              className="form-select"
            >
              <option value="">Select Property...</option>
              {properties.map(prop => (
                <option key={prop.id} value={prop.id}>{prop.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 'var(--spacing-md)', marginTop: 'var(--spacing-xl)' }}>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={loading || !accountId || !propertyId}
            style={{ flex: 2, justifyContent: 'center' }}
          >
            {loading ? "SAVING..." : "COMPLETE REVIEW"}
          </button>
          <button className="btn-secondary" onClick={onCancel} disabled={loading} style={{ flex: 1, justifyContent: 'center' }}>
            CANCEL
          </button>
        </div>
      </div>
    </div>
  );
};

const BulkEditModal = ({ selectedCount, accounts, properties, onSave, onCancel }) => {
  const [accountId, setAccountId] = useState('');
  const [propertyId, setPropertyId] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSave = async () => {
    if (!accountId || !propertyId) {
      showNotification("Please select both an Account and a Property for bulk update.", "warning");
      return;
    }
    setLoading(true);
    try {
      await onSave({ account_id: accountId, property_id: propertyId });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="premium-card modal-content" style={{ maxWidth: '500px', width: '100%', padding: 'var(--spacing-xl)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--spacing-xl)' }}>
          <div>
            <label>Bulk Action</label>
            <h2 style={{ fontSize: '28px', margin: 0 }}>Edit {selectedCount} Items</h2>
          </div>
          <button onClick={onCancel} style={{ background: 'none', border: 'none', color: 'var(--text-main)', cursor: 'pointer' }}>
            <X size={24} />
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
          <div>
            <label>Set Category for All</label>
            <select value={accountId} onChange={(e) => setAccountId(e.target.value)} className="form-select">
              <option value="">Select Category...</option>
              {accounts.map(acc => (
                <option key={acc.id} value={acc.id}>{acc.code} - {acc.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label>Set Property for All</label>
            <select value={propertyId} onChange={(e) => setPropertyId(e.target.value)} className="form-select">
              <option value="">Select Property...</option>
              {properties.map(prop => (
                <option key={prop.id} value={prop.id}>{prop.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 'var(--spacing-md)', marginTop: 'var(--spacing-xl)' }}>
          <button className="btn-primary" onClick={handleSave} disabled={loading || !accountId || !propertyId} style={{ flex: 1, justifyContent: 'center' }}>
            {loading ? "UPDATING..." : "APPLY TO ALL"}
          </button>
          <button className="btn-secondary" onClick={onCancel} disabled={loading} style={{ flex: 1, justifyContent: 'center' }}>
            CANCEL
          </button>
        </div>
      </div>
    </div>
  );
};

const ReviewQueue = ({ entityId }) => {
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAiReasoning, setShowAiReasoning] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const [editingTx, setEditingTx] = useState(null);
  const [isBulkEditing, setIsBulkEditing] = useState(false);
  const [accounts, setAccounts] = useState([]);
  const [properties, setProperties] = useState([]);
  const [searchParams] = useSearchParams();
  const highlightedTxId = searchParams.get('tx_id');
  const rowRefs = useRef({});
  const { showNotification } = useNotification();
  const [confirm, setConfirm] = useState({ isOpen: false, title: '', message: '', onConfirm: null, danger: false });
  const closeConfirm = () => setConfirm(prev => ({ ...prev, isOpen: false }));

  useEffect(() => {
    fetchMetadata();
    if (entityId) {
      fetchQueue();
    }
  }, [entityId]);

  useEffect(() => {
    if (highlightedTxId && queue.length > 0) {
      const row = rowRefs.current[highlightedTxId];
      if (row) {
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [highlightedTxId, queue]);

  const fetchMetadata = async () => {
    try {
      const [accRes, propRes] = await Promise.all([
        axios.get(`${API_BASE}/meta/accounts`),
        axios.get(`${API_BASE}/meta/properties`)
      ]);
      setAccounts(accRes.data.data);
      setProperties(propRes.data.data);
    } catch (err) {
      console.error("Error fetching metadata", err);
    }
  };

  const fetchQueue = async () => {
    try {
      const response = await axios.get(`${API_BASE}/queue/?entity_id=${entityId}`);
      setQueue(response.data.data);
      setSelectedIds([]);
    } catch (err) {
      console.error("Error fetching queue", err);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (txId) => {
    try {
      await axios.post(`${API_BASE}/queue/${txId}/approve`);
      setQueue(prev => prev.filter(tx => tx.id !== txId));
      setSelectedIds(prev => prev.filter(id => id !== txId));
    } catch (err) {
      const status = err.response?.status ? `[${err.response.status}]` : '';
      const detail = err.response?.data?.detail || err.message;
      showNotification(`Failed to approve transaction ${status}: ${detail}`, "error");
    }
  };

  const handleBulkApprove = async () => {
    if (selectedIds.length === 0) return;
    setProcessing(true);
    try {
      await Promise.all(selectedIds.map(id => axios.post(`${API_BASE}/queue/${id}/approve`)));
      setQueue(prev => prev.filter(tx => !selectedIds.includes(tx.id)));
      setSelectedIds([]);
      showNotification("Selected transactions approved.", "success");
    } catch (err) {
      const status = err.response?.status ? `[${err.response.status}]` : '';
      const detail = err.response?.data?.detail || err.message;
      showNotification(`Failed to approve transactions ${status}: ${detail}`, 'error');
      fetchQueue();
    } finally {
      setProcessing(false);
    }
  };

  const handleExclude = (txId) => {
    setConfirm({
      isOpen: true,
      title: 'Exclude Transaction',
      message: 'Exclude this transaction from the review queue? It will be marked as excluded and removed from this list.',
      danger: true,
      onConfirm: async () => {
        closeConfirm();
        try {
          await axios.post(`${API_BASE}/queue/${txId}/exclude`);
          setQueue(prev => prev.filter(tx => tx.id !== txId));
          setSelectedIds(prev => prev.filter(id => id !== txId));
        } catch (err) {
          const status = err.response?.status ? `[${err.response.status}]` : '';
          const detail = err.response?.data?.detail || err.message;
          showNotification(`Failed to exclude transaction ${status}: ${detail}`, 'error');
        }
      },
    });
  };

  const handleSaveCorrection = async (txId, data) => {
    try {
      await axios.post(`${API_BASE}/queue/${txId}/correct`, data);
      setQueue(prev => prev.filter(tx => tx.id !== txId));
      setSelectedIds(prev => prev.filter(id => id !== txId));
      setEditingTx(null);
    } catch (err) {
      const status = err.response?.status ? `[${err.response.status}]` : '';
      const detail = err.response?.data?.detail || err.message;
      showNotification(`Failed to save changes ${status}: ${detail}`, "error");
    }
  };

  const handleBulkSave = async (data) => {
    try {
      // Process sequential for safety or add a bulk endpoint
      const promises = selectedIds.map(txId => {
        const tx = queue.find(q => q.id === txId);
        return axios.post(`${API_BASE}/queue/${txId}/correct`, {
          account_id: data.account_id,
          allocations: [{ property_id: data.property_id, amount: tx.amount }]
        });
      });
      await Promise.all(promises);
      setQueue(prev => prev.filter(tx => !selectedIds.includes(tx.id)));
      setSelectedIds([]);
      setIsBulkEditing(false);
    } catch (err) {
      const status = err.response?.status ? `[${err.response.status}]` : '';
      const detail = err.response?.data?.detail || err.message;
      showNotification(`Failed to update some transactions ${status}: ${detail}`, "error");
      fetchQueue();
    }
  };

  const toggleSelect = (txId) => {
    setSelectedIds(prev =>
      prev.includes(txId) ? prev.filter(id => id !== txId) : [...prev, txId]
    );
  };

  const toggleSelectAll = () => {
    if (selectedIds.length === queue.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(queue.map(tx => tx.id));
    }
  };

  const handleSync = async () => {
    setLoading(true);
    try {
      await axios.post(`${API_BASE}/plaid/sync`, { entity_id: entityId });
      fetchQueue();
    } catch (err) {
      showNotification("Failed to initiate sync.", "error");
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const badges = {
      'pending_review': <span className="badge badge-pending">Review</span>,
      'ai_suggested': <span className="badge badge-suggested">AI Suggested</span>,
      'flagged': <span className="badge badge-flagged">Flagged</span>
    };
    return badges[status] || status;
  };

  return (
    <div className="premium-card" style={{ padding: 0 }}>
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-light)', display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '10px' }}>
        <div style={{ minWidth: 0 }}>
          <h2 style={{ fontSize: '20px', margin: 0, whiteSpace: 'nowrap' }}>Transactions for Review</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '12px', fontWeight: 600, margin: 0 }}>
            {selectedIds.length > 0 ? `${selectedIds.length} selected` : `${queue.length} items requiring classification`}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', flexShrink: 0 }}>
          <button
            className={`btn-secondary`}
            onClick={() => setShowAiReasoning(!showAiReasoning)}
            style={{
              background: showAiReasoning ? 'rgba(193, 155, 46, 0.1)' : 'transparent',
              borderColor: showAiReasoning ? 'var(--primary-gold)' : 'var(--border-light)',
              padding: '8px 12px',
              fontSize: '11px'
            }}
          >
            {showAiReasoning ? 'Hide AI' : 'Show AI'}
          </button>
          {selectedIds.length > 0 && (
            <button className="btn-primary" onClick={() => setIsBulkEditing(true)} style={{ background: 'var(--primary-gold)', color: '#000', padding: '8px 12px', fontSize: '11px' }}>
              <Layers size={14} />
            </button>
          )}
          <button
            className="btn-primary"
            onClick={handleBulkApprove}
            disabled={selectedIds.length === 0 || processing}
            style={{ padding: '8px 12px', fontSize: '11px' }}
          >
            <CheckCircle2 size={14} /> <span style={{ marginLeft: '6px' }}>APPROVE {selectedIds.length > 0 ? `(${selectedIds.length})` : ''}</span>
          </button>
          <button className="btn-primary" onClick={handleSync} disabled={loading} style={{ padding: '8px 12px', fontSize: '11px' }}>
            {loading ? 'SYNCING...' : 'SYNC'}
          </button>
        </div>
      </div>

      {/* Desktop Table */}
      <div className="desktop-table-only table-container">
        <table style={{ minWidth: '1050px', tableLayout: 'fixed' }}>
          <colgroup>
            <col style={{ width: '40px' }} />
            <col style={{ width: '105px' }} />
            <col style={{ width: '220px' }} />
            <col style={{ width: '130px' }} />
            <col style={{ width: '110px' }} />
            <col style={{ width: '120px' }} />
            <col style={{ width: '160px' }} />
            <col style={{ width: '150px' }} />
            <col style={{ width: '115px' }} />
          </colgroup>
          <thead>
            <tr>
              <th>
                <input type="checkbox" checked={queue.length > 0 && selectedIds.length === queue.length} onChange={toggleSelectAll} />
              </th>
              <th>Date</th>
              <th>Counterparty / Vendor</th>
              <th className="hide-mobile">Account</th>
              <th style={{ textAlign: 'right' }}>Amount</th>
              <th className="hide-mobile">Classification</th>
              <th>Suggested Category</th>
              <th className="hide-mobile">Suggested Property</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {queue.map(tx => (
              <tr
                key={tx.id}
                ref={el => rowRefs.current[tx.id] = el}
                className={`${selectedIds.includes(tx.id) ? 'selected-row' : ''} ${highlightedTxId === tx.id ? 'highlighted-row' : ''}`}
              >
                <td>
                  <input type="checkbox" checked={selectedIds.includes(tx.id)} onChange={() => toggleSelect(tx.id)} />
                </td>
                <td style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)' }}>{tx.transaction_date}</td>
                <td style={{ maxWidth: '250px', overflow: 'hidden' }}>
                  <div style={{ fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.02em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{tx.vendor_name_clean || "Direct Deposit/Draft"}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {tx.status === 'ai_suggested' && tx.categorization_reason && showAiReasoning ?
                      `AI: ${tx.categorization_reason.split(' ').slice(0, 12).join(' ')}${tx.categorization_reason.split(' ').length > 12 ? '...' : ''}`
                      : `REF: ${tx.id.substring(0, 8)}`}
                  </div>
                </td>
                <td className="hide-mobile">
                  <div style={{ fontSize: '13px', fontWeight: 700 }}>{tx.bank_name || 'Manual'}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>****{tx.account_last4 || 'N/A'}</div>
                </td>
                <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }} className={`amount ${tx.amount < 0 ? 'negative' : 'positive'}`}>
                  {tx.amount < 0 ? `-$${Math.abs(tx.amount).toFixed(2)}` : `+$${tx.amount.toFixed(2)}`}
                </td>
                <td className="hide-mobile" style={{ whiteSpace: 'nowrap' }}>{getStatusBadge(tx.status)}</td>
                <td style={{ overflow: 'hidden' }}>
                  {tx.category_name ? (
                    <span style={{ fontWeight: 700, color: 'var(--text-main)', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{tx.category_name}</span>
                  ) : (
                    <span style={{ color: '#ba1a1a', fontWeight: 700 }}>UNASSIGNED</span>
                  )}
                </td>
                <td className="hide-mobile" style={{ overflow: 'hidden' }}>
                  {tx.property_names ? (
                    <span style={{ fontWeight: 700, color: 'var(--text-main)', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{tx.property_names}</span>
                  ) : (
                    <span style={{ color: '#ba1a1a', fontWeight: 700 }}>UNASSIGNED</span>
                  )}
                </td>
                <td style={{ textAlign: 'right' }}>
                  <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                    <button onClick={() => handleApprove(tx.id)} className="btn-secondary" style={{ padding: '8px', color: '#111' }} title="Approve">
                      <Check size={16} />
                    </button>
                    <button onClick={() => setEditingTx(tx)} className="btn-secondary" style={{ padding: '8px' }} title="Correct">
                      <Edit3 size={16} />
                    </button>
                    <button onClick={() => handleExclude(tx.id)} className="btn-secondary" style={{ padding: '8px', color: '#ba1a1a' }} title="Exclude">
                      <Trash2 size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {queue.length === 0 && !loading && (
              <tr>
                <td colSpan="9" style={{ textAlign: 'center', padding: 'var(--spacing-xl)' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--spacing-md)' }}>
                    <CheckCircle2 size={48} color="var(--primary-gold)" />
                    <h3 style={{ margin: 0 }}>Queue Cleared</h3>
                    <p style={{ color: 'var(--text-muted)', fontSize: '14px' }}>All transactions have been successfully categorized.</p>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile Card List */}
      <div className="mobile-card-list">
        {queue.length === 0 && !loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', padding: '40px 16px', textAlign: 'center' }}>
            <CheckCircle2 size={40} color="var(--primary-gold)" />
            <h3 style={{ margin: 0, fontSize: '18px' }}>Queue Cleared</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: 0 }}>All transactions have been successfully categorized.</p>
          </div>
        ) : (
          queue.map(tx => (
            <div
              key={tx.id}
              ref={el => rowRefs.current[tx.id] = el}
              className={`rq-mobile-card ${selectedIds.includes(tx.id) ? 'rq-card-selected' : ''} ${highlightedTxId === tx.id ? 'highlighted-row' : ''}`}
            >
              <div className="rq-card-top">
                <input type="checkbox" checked={selectedIds.includes(tx.id)} onChange={() => toggleSelect(tx.id)} style={{ flexShrink: 0 }} />
                <span className="rq-card-date">{tx.transaction_date}</span>
                <span className={`rq-card-amount amount ${tx.amount < 0 ? 'negative' : 'positive'}`}>
                  {tx.amount < 0 ? `-$${Math.abs(tx.amount).toFixed(2)}` : `+$${tx.amount.toFixed(2)}`}
                </span>
              </div>
              <div className="rq-card-vendor">{tx.vendor_name_clean || 'Direct Deposit/Draft'}</div>
              {showAiReasoning && tx.categorization_reason && (
                <div className="rq-card-reason">AI: {tx.categorization_reason.split(' ').slice(0, 14).join(' ')}{tx.categorization_reason.split(' ').length > 14 ? '...' : ''}</div>
              )}
              <div className="rq-card-bottom">
                <span className="rq-card-category">
                  {tx.category_name
                    ? tx.category_name
                    : <span style={{ color: '#ba1a1a' }}>UNASSIGNED</span>}
                </span>
                <div className="rq-card-actions">
                  <button onClick={() => handleApprove(tx.id)} className="btn-secondary rq-action-btn" title="Approve">
                    <Check size={14} />
                  </button>
                  <button onClick={() => setEditingTx(tx)} className="btn-secondary rq-action-btn" title="Edit">
                    <Edit3 size={14} />
                  </button>
                  <button onClick={() => handleExclude(tx.id)} className="btn-secondary rq-action-btn" style={{ color: '#ba1a1a' }} title="Exclude">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {editingTx && (
        <EditModal
          transaction={editingTx}
          accounts={accounts}
          properties={properties}
          onSave={handleSaveCorrection}
          onCancel={() => setEditingTx(null)}
        />
      )}

      {isBulkEditing && (
        <BulkEditModal
          selectedCount={selectedIds.length}
          accounts={accounts}
          properties={properties}
          onSave={handleBulkSave}
          onCancel={() => setIsBulkEditing(false)}
        />
      )}

      <ConfirmModal
        isOpen={confirm.isOpen}
        title={confirm.title}
        message={confirm.message}
        confirmText="Exclude"
        cancelText="Cancel"
        danger={confirm.danger}
        onConfirm={confirm.onConfirm}
        onCancel={closeConfirm}
      />

      <style>{`
        .selected-row { background: rgba(212, 175, 55, 0.05); }
        .highlighted-row {
          background: rgba(212, 175, 55, 0.25) !important;
          outline: 3px solid var(--primary-gold);
          outline-offset: -3px;
          animation: pulseHighlight 1.5s ease-in-out infinite;
          z-index: 10;
          position: relative;
        }
        @keyframes pulseHighlight {
          0% { background: rgba(212, 175, 55, 0.15); box-shadow: inset 0 0 0 0 rgba(212, 175, 55, 0); }
          50% { background: rgba(212, 175, 55, 0.4); box-shadow: inset 0 0 20px 0 rgba(212, 175, 55, 0.3); }
          100% { background: rgba(212, 175, 55, 0.15); box-shadow: inset 0 0 0 0 rgba(212, 175, 55, 0); }
        }
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(17, 17, 17, 0.85);
          backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 1rem;
        }
        .modal-content {
          animation: slideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }
        @keyframes slideUp {
          from { transform: translateY(20px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }

        /* Mobile cards */
        .rq-mobile-card {
          padding: 12px 14px;
          border-bottom: 1px solid var(--border-light);
          display: flex;
          flex-direction: column;
          gap: 6px;
          background: #fff;
          transition: background 0.15s;
        }
        .rq-mobile-card:last-child { border-bottom: none; }
        .rq-card-selected { background: rgba(212, 175, 55, 0.06) !important; }
        .rq-card-top {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .rq-card-date {
          flex: 1;
          font-size: 11px;
          font-weight: 700;
          color: var(--text-muted);
          letter-spacing: 0.02em;
        }
        .rq-card-amount {
          font-size: 15px;
          font-weight: 800;
          flex-shrink: 0;
        }
        .rq-card-vendor {
          font-size: 13px;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: 0.03em;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          color: var(--text-main);
        }
        .rq-card-reason {
          font-size: 11px;
          color: var(--text-muted);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-style: italic;
        }
        .rq-card-bottom {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          margin-top: 2px;
        }
        .rq-card-category {
          font-size: 12px;
          font-weight: 700;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          flex: 1;
        }
        .rq-card-actions {
          display: flex;
          gap: 4px;
          flex-shrink: 0;
        }
        .rq-action-btn {
          padding: 6px 8px !important;
          display: flex;
          align-items: center;
          justify-content: center;
        }
      `}</style>
    </div>
  );
};

export default ReviewQueue;

