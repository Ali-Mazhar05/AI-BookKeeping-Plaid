import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { createPortal } from 'react-dom';
import axios from 'axios';
import { Search, Download, Edit3, Trash2, X } from 'lucide-react';
import { useNotification } from './Notification';
import ConfirmModal from './ConfirmModal';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const EditModal = ({ transaction, accounts, properties, onSave, onCancel }) => {
  const [accountId, setAccountId] = useState(transaction.account_id || '');
  const [propertyId, setPropertyId] = useState('');
  const [loading, setLoading] = useState(false);
  const { showNotification } = useNotification();

  useEffect(() => {
    if (transaction.property_names && properties.length > 0) {
      const match = properties.find(p => transaction.property_names.includes(p.name));
      if (match) setPropertyId(match.id);
    }
  }, [transaction, properties]);

  const handleSave = async () => {
    if (!accountId || !propertyId) {
      showNotification('Please select both a Category and a Property.', 'warning');
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

  return createPortal(
    <div className="modal-overlay">
      <div className="premium-card modal-content" style={{ maxWidth: '560px', width: '100%', padding: 'var(--spacing-xl)', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--spacing-xl)' }}>
          <div>
            <label>Edit Record</label>
            <h2 style={{ fontSize: '28px', margin: 0 }}>Update Transaction</h2>
          </div>
          <button onClick={onCancel} style={{ background: 'none', border: 'none', color: 'var(--text-main)', cursor: 'pointer' }}>
            <X size={24} />
          </button>
        </div>

        <div style={{ marginBottom: 'var(--spacing-xl)', paddingBottom: 'var(--spacing-lg)', borderBottom: '1px solid var(--border-light)' }}>
          <div style={{ fontSize: '18px', fontWeight: 700, fontFamily: 'var(--font-headline)' }}>{transaction.vendor_name_clean || transaction.merchant_name || 'Direct Entry'}</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '13px', fontWeight: 600, marginTop: '4px' }}>
            {transaction.transaction_date} &bull; {transaction.amount < 0 ? `-$${Math.abs(transaction.amount).toFixed(2)}` : `+$${transaction.amount.toFixed(2)}`}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
          <div>
            <label>Chart of Account (Category)</label>
            <select value={accountId} onChange={(e) => setAccountId(e.target.value)} className="form-select">
              <option value="">Select Category...</option>
              {accounts.map(acc => (
                <option key={acc.id} value={acc.id}>{acc.code} - {acc.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label>Property Attribution</label>
            <select value={propertyId} onChange={(e) => setPropertyId(e.target.value)} className="form-select">
              <option value="">Select Property...</option>
              {properties.map(prop => (
                <option key={prop.id} value={prop.id}>{prop.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 'var(--spacing-md)', marginTop: 'var(--spacing-xl)' }}>
          <button className="btn-primary" onClick={handleSave} disabled={loading || !accountId || !propertyId} style={{ flex: 2, justifyContent: 'center' }}>
            {loading ? 'SAVING...' : 'SAVE CHANGES'}
          </button>
          <button className="btn-secondary" onClick={onCancel} disabled={loading} style={{ flex: 1, justifyContent: 'center' }}>
            CANCEL
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

const TransactionSection = ({ entityId }) => {
  const [transactions, setTransactions] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [properties, setProperties] = useState([]);

  const [selectedAccount, setSelectedAccount] = useState('');
  const [searchParams] = useSearchParams();
  const initialPropertyId = searchParams.get('property_id') || '';
  const initialCategoryId = searchParams.get('category_id') || '';
  const [selectedCategory, setSelectedCategory] = useState(initialCategoryId);
  const [selectedProperty, setSelectedProperty] = useState(initialPropertyId);

  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortOrder, setSortOrder] = useState('latest');
  const [editingTx, setEditingTx] = useState(null);
  const [confirm, setConfirm] = useState({ isOpen: false, title: '', message: '', onConfirm: null });
  const closeConfirm = () => setConfirm(prev => ({ ...prev, isOpen: false }));
  const { showNotification } = useNotification();

  useEffect(() => {
    const propId = searchParams.get('property_id');
    const catId = searchParams.get('category_id');
    if (propId) setSelectedProperty(propId);
    if (catId) setSelectedCategory(catId);
  }, [searchParams]);

  useEffect(() => {
    fetchMetadata();
    fetchTransactions();
  }, [entityId, selectedAccount]);

  const fetchMetadata = async () => {
    try {
      const [bankRes, catRes, propRes] = await Promise.all([
        axios.get(`${API_BASE}/meta/bank-accounts`),
        axios.get(`${API_BASE}/meta/accounts`),
        axios.get(`${API_BASE}/meta/properties`)
      ]);
      setBankAccounts(bankRes.data.data);
      setCategories(catRes.data.data);
      setProperties(propRes.data.data);
    } catch (err) {
      console.error('Error fetching metadata', err);
    }
  };

  const fetchTransactions = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('entity_id', entityId);
      if (selectedAccount) params.append('bank_account_id', selectedAccount);

      const response = await axios.get(`${API_BASE}/transactions/?${params.toString()}`);
      setTransactions(response.data.data);
    } catch (err) {
      console.error('Error fetching transactions', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = (txId) => {
    setConfirm({
      isOpen: true,
      title: 'Delete Transaction',
      message: 'Permanently delete this transaction and all its property allocations? This cannot be undone.',
      onConfirm: async () => {
        closeConfirm();
        try {
          await axios.delete(`${API_BASE}/transactions/${txId}`);
          setTransactions(prev => prev.filter(t => t.id !== txId));
          showNotification('Transaction deleted.', 'success');
        } catch (err) {
          const status = err.response?.status ? `[${err.response.status}]` : '';
          const detail = err.response?.data?.detail || err.message;
          showNotification(`Failed to delete transaction ${status}: ${detail}`, 'error');
        }
      },
    });
  };

  const handleSaveEdit = async (txId, data) => {
    try {
      await axios.patch(`${API_BASE}/transactions/${txId}`, data);
      setEditingTx(null);
      fetchTransactions();
    } catch (err) {
      const status = err.response?.status ? `[${err.response.status}]` : '';
      const detail = err.response?.data?.detail || err.message;
      showNotification(`Failed to update transaction ${status}: ${detail}`, 'error');
    }
  };

  const filteredTransactions = transactions.filter(tx => {
    const matchesSearch = (tx.vendor_name_clean || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (tx.description_clean || '').toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory ? (tx.account_id === selectedCategory) : true;
    const matchesProperty = selectedProperty ?
      (tx.property_names && tx.property_names.includes(properties.find(p => p.id === selectedProperty)?.name))
      : true;
    return matchesSearch && matchesCategory && matchesProperty;
  }).sort((a, b) => {
    const dateA = new Date(a.transaction_date);
    const dateB = new Date(b.transaction_date);
    return (sortOrder === 'latest' || sortOrder === 'recent') ? dateB - dateA : dateA - dateB;
  });

  const exportToCSV = () => {
    const headers = ['Date', 'Vendor', 'Description', 'Amount', 'Category', 'Properties', 'Bank', 'Account', 'Status'];
    const rows = filteredTransactions.map(tx => [
      tx.transaction_date,
      tx.merchant_name || tx.vendor_name_clean || 'Direct Entry',
      tx.description_clean || '',
      tx.amount.toFixed(2),
      tx.category_name || tx.plaid_category_primary || 'Unassigned',
      tx.property_names || '',
      tx.bank_name || '',
      tx.account_last4 ? `****${tx.account_last4}` : '',
      tx.status || ''
    ]);
    const escape = (val) => `"${String(val).replace(/"/g, '""')}"`;
    const csv = [headers, ...rows].map(row => row.map(escape).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transactions_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getStatusBadge = (status) => {
    const badges = {
      'reviewed': <span className="badge" style={{ background: '#111', color: '#fff' }}>Reviewed</span>,
      'auto_categorized': <span className="badge badge-suggested">AI Verified</span>,
      'pending_review': <span className="badge badge-pending">Pending</span>,
      'flagged': <span className="badge badge-flagged">Flagged</span>,
      'excluded': <span className="badge badge-pending">Excluded</span>
    };
    return badges[status] || <span className="badge">{status}</span>;
  };

  return (
    <div className="premium-card" style={{ padding: 0, overflow: 'visible' }}>
      {/* Header */}
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <h2 style={{ fontSize: '20px', margin: 0, whiteSpace: 'nowrap' }}>Historical Ledger</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '12px', fontWeight: 600, margin: 0 }}>Archived records for all connected institutions.</p>
        </div>
        <button className="btn-secondary" onClick={exportToCSV} disabled={filteredTransactions.length === 0} style={{ flexShrink: 0, padding: '8px 12px', fontSize: '11px' }}>
          <Download size={14} /> <span style={{ marginLeft: '6px' }}>EXPORT ({filteredTransactions.length})</span>
        </button>
      </div>

      {/* Filters */}
      <div style={{ padding: '12px 14px', background: '#F9F9F9', display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-light)', flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 200px', position: 'relative', minWidth: '140px' }}>
          <Search style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} size={14} />
          <input
            type="text"
            placeholder="Search..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="form-input"
            style={{ paddingLeft: '34px', fontSize: '13px', height: '40px' }}
          />
        </div>
        <select value={selectedAccount} onChange={(e) => setSelectedAccount(e.target.value)} className="form-select" style={{ flex: '1 1 130px', minWidth: '130px', fontSize: '12px', height: '43px' }}>
          <option value="">All Bank Accounts</option>
          {bankAccounts.map(acc => (
            <option key={acc.id} value={acc.id}>{acc.bank_name} ****{acc.account_last4}</option>
          ))}
        </select>
        <select value={selectedCategory} onChange={(e) => setSelectedCategory(e.target.value)} className="form-select" style={{ flex: '1 1 130px', minWidth: '130px', fontSize: '12px', height: '43px' }}>
          <option value="">All Categories</option>
          {categories.map(cat => (
            <option key={cat.id} value={cat.id}>{cat.name}</option>
          ))}
        </select>
        <select value={selectedProperty} onChange={(e) => setSelectedProperty(e.target.value)} className="form-select" style={{ flex: '1 1 130px', minWidth: '130px', fontSize: '12px', height: '43px' }}>
          <option value="">All Properties</option>
          {properties.map(prop => (
            <option key={prop.id} value={prop.id}>{prop.name}</option>
          ))}
        </select>
        <select value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} className="form-select" style={{ flex: '1 1 100px', minWidth: '100px', fontSize: '12px', height: '43px', fontWeight: 700, borderLeft: '3px solid var(--primary-gold)' }}>
          <option value="latest">Latest</option>
          <option value="earliest">Earliest</option>
        </select>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)', fontSize: '13px' }}>Synchronizing ledger data...</div>
      ) : (
        <>
          {/* Desktop Table */}
          <div className="desktop-table-only table-container" style={{ overflowX: 'auto' }}>
            <table style={{ minWidth: '960px' }}>
              <thead>
                <tr>
                  <th style={{ width: '100px' }}>Date</th>
                  <th>Counterparty</th>
                  <th>Category</th>
                  <th>Properties</th>
                  <th>Source</th>
                  <th style={{ textAlign: 'right' }}>Amount</th>
                  <th style={{ textAlign: 'center' }}>Status</th>
                  <th style={{ textAlign: 'right', width: '90px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredTransactions.map(tx => (
                  <tr key={tx.id}>
                    <td style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)' }}>{tx.transaction_date}</td>
                    <td style={{ maxWidth: '200px', overflow: 'hidden' }}>
                      <div style={{ fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.02em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{tx.merchant_name || tx.vendor_name_clean || 'Direct Entry'}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>ID: {tx.id.substring(0, 8)}</div>
                    </td>
                    <td style={{ maxWidth: '180px', overflow: 'hidden' }}>
                      <div style={{ fontSize: '13px', fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{tx.category_name || tx.plaid_category_primary || 'Unassigned'}</div>
                    </td>
                    <td style={{ maxWidth: '180px', overflow: 'hidden' }}>
                      <div style={{ fontSize: '12px', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{tx.property_names || 'None'}</div>
                    </td>
                    <td>
                      <div style={{ fontSize: '13px', fontWeight: 700 }}>{tx.bank_name}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>****{tx.account_last4}</div>
                    </td>
                    <td style={{ textAlign: 'right' }} className={`amount ${tx.amount < 0 ? 'negative' : 'positive'}`}>
                      {tx.amount < 0 ? `-$${Math.abs(tx.amount).toFixed(2)}` : `+$${tx.amount.toFixed(2)}`}
                    </td>
                    <td style={{ textAlign: 'center' }}>{getStatusBadge(tx.status)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '4px', justifyContent: 'flex-end' }}>
                        <button onClick={() => setEditingTx(tx)} className="btn-secondary" style={{ padding: '6px 8px' }} title="Edit">
                          <Edit3 size={14} />
                        </button>
                        <button onClick={() => handleDelete(tx.id)} className="btn-secondary" style={{ padding: '6px 8px', color: '#ba1a1a' }} title="Delete">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredTransactions.length === 0 && (
                  <tr>
                    <td colSpan="8" style={{ textAlign: 'center', padding: 'var(--spacing-xl)', color: 'var(--text-muted)' }}>
                      No matching records found in the ledger.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Mobile Card List */}
          <div className="mobile-card-list">
            {filteredTransactions.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 16px', color: 'var(--text-muted)', fontSize: '13px' }}>
                No matching records found in the ledger.
              </div>
            ) : (
              filteredTransactions.map(tx => (
                <div key={tx.id} className="ledger-mobile-card">
                  <div className="lmc-top">
                    <span className="lmc-date">{tx.transaction_date}</span>
                    <span className={`lmc-amount amount ${tx.amount < 0 ? 'negative' : 'positive'}`}>
                      {tx.amount < 0 ? `-$${Math.abs(tx.amount).toFixed(2)}` : `+$${tx.amount.toFixed(2)}`}
                    </span>
                  </div>
                  <div className="lmc-vendor">{tx.merchant_name || tx.vendor_name_clean || 'Direct Entry'}</div>
                  <div className="lmc-meta">
                    <span className="lmc-category">{tx.category_name || 'Unassigned'}</span>
                    <span className="lmc-dot">&bull;</span>
                    <span className="lmc-property">{tx.property_names || 'No Property'}</span>
                  </div>
                  <div className="lmc-bottom-row">
                    {getStatusBadge(tx.status)}
                    <div style={{ display: 'flex', gap: '4px' }}>
                      <button onClick={() => setEditingTx(tx)} className="btn-secondary" style={{ padding: '5px 7px' }} title="Edit">
                        <Edit3 size={13} />
                      </button>
                      <button onClick={() => handleDelete(tx.id)} className="btn-secondary" style={{ padding: '5px 7px', color: '#ba1a1a' }} title="Delete">
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </>
      )}

      {editingTx && (
        <EditModal
          transaction={editingTx}
          accounts={categories}
          properties={properties}
          onSave={handleSaveEdit}
          onCancel={() => setEditingTx(null)}
        />
      )}

      <ConfirmModal
        isOpen={confirm.isOpen}
        title={confirm.title}
        message={confirm.message}
        confirmText="Delete"
        cancelText="Cancel"
        danger={true}
        onConfirm={confirm.onConfirm}
        onCancel={closeConfirm}
      />

      <style>{`
        .ledger-mobile-card {
          padding: 12px 14px;
          border-bottom: 1px solid var(--border-light);
          display: flex;
          flex-direction: column;
          gap: 4px;
          background: #fff;
        }
        .ledger-mobile-card:last-child { border-bottom: none; }
        .lmc-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .lmc-date { font-size: 11px; font-weight: 700; color: var(--text-muted); letter-spacing: 0.02em; }
        .lmc-amount { font-size: 15px; font-weight: 800; }
        .lmc-vendor {
          font-size: 13px; font-weight: 800; text-transform: uppercase;
          letter-spacing: 0.03em; overflow: hidden; text-overflow: ellipsis;
          white-space: nowrap; color: var(--text-main);
        }
        .lmc-meta {
          display: flex; align-items: center; gap: 6px;
          font-size: 11px; color: var(--text-muted); font-weight: 600; overflow: hidden;
        }
        .lmc-category, .lmc-property { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex-shrink: 1; }
        .lmc-dot { flex-shrink: 0; }
        .lmc-bottom-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-top: 2px;
        }
      `}</style>
    </div>
  );
};

export default TransactionSection;
