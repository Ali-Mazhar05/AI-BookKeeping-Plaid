import React, { useState } from 'react';
import { X, Link2, PenLine } from 'lucide-react';
import axios from 'axios';
import PlaidLinkButton from './PlaidLinkButton';
import { useNotification } from './Notification';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const AddAccountModal = ({ entityId, onClose, onSuccess }) => {
  const { showNotification } = useNotification();
  const [tab, setTab] = useState('plaid');
  const [formData, setFormData] = useState({
    bank_name: '',
    account_name: '',
    account_last4: '',
    account_type: 'checking',
  });
  const [loading, setLoading] = useState(false);

  const handleManualSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post(`${API_BASE}/bank-accounts/manual`, { ...formData, entity_id: entityId });
      showNotification('Bank account added successfully.', 'success');
      onSuccess();
      onClose();
    } catch (err) {
      showNotification(err.response?.data?.detail || 'Failed to create account', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handlePlaidSuccess = () => {
    onSuccess();
    onClose();
  };

  const tabs = [
    { key: 'plaid',  icon: <Link2 size={15} />,   label: 'Connect via Plaid', sub: 'Auto-sync · Recommended' },
    { key: 'manual', icon: <PenLine size={15} />,  label: 'Add Manually',      sub: 'No automatic sync' },
  ];

  return (
    <div className="modal-overlay">
      <div className="premium-card modal-content" style={{ maxWidth: '500px', width: '92%' }}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '20px', margin: 0 }}>Add Bank Account</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', lineHeight: 0 }}>
            <X size={20} />
          </button>
        </div>

        {/* Tab toggle */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '24px' }}>
          {tabs.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '5px',
                padding: '14px 10px', cursor: 'pointer', borderRadius: '4px', transition: 'all 0.15s',
                border: `2px solid ${tab === t.key ? 'var(--primary-gold)' : 'var(--border-light)'}`,
                background: tab === t.key ? 'rgba(193,155,46,0.07)' : 'transparent',
              }}
            >
              <span style={{ color: tab === t.key ? 'var(--primary-gold)' : 'var(--text-muted)' }}>{t.icon}</span>
              <span style={{ fontSize: '11px', fontWeight: 800, letterSpacing: '0.05em', color: tab === t.key ? 'inherit' : 'var(--text-muted)' }}>
                {t.label}
              </span>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>{t.sub}</span>
            </button>
          ))}
        </div>

        {/* ── Plaid tab ── */}
        {tab === 'plaid' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px', paddingBottom: '8px' }}>
            <div style={{ textAlign: 'center', maxWidth: '360px' }}>
              <div style={{
                width: '52px', height: '52px', borderRadius: '50%',
                background: 'rgba(193,155,46,0.1)', display: 'flex',
                alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px',
              }}>
                <Link2 size={26} color="var(--primary-gold)" />
              </div>
              <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>Secure Bank Connection</h3>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.65, margin: 0 }}>
                Connect through Plaid. Transactions are imported automatically, categorized by AI, and placed in your review queue — starting immediately.
              </p>
            </div>

            <PlaidLinkButton
              entityId={entityId}
              onLinkSuccess={handlePlaidSuccess}
              label="CONNECT BANK ACCOUNT"
              className="btn-primary"
            />

            <p style={{ fontSize: '10px', color: 'var(--text-muted)', textAlign: 'center', margin: 0, letterSpacing: '0.04em' }}>
              BANK-LEVEL ENCRYPTION · READ-ONLY ACCESS · NIGHTLY SYNC AT 4 AM
            </p>
          </div>
        )}

        {/* ── Manual tab ── */}
        {tab === 'manual' && (
          <form onSubmit={handleManualSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label>Bank Name</label>
              <input
                type="text" required
                value={formData.bank_name}
                onChange={e => setFormData({ ...formData, bank_name: e.target.value })}
                placeholder="e.g. Chase, Wells Fargo"
              />
            </div>
            <div>
              <label>Account Name</label>
              <input
                type="text" required
                value={formData.account_name}
                onChange={e => setFormData({ ...formData, account_name: e.target.value })}
                placeholder="e.g. Business Checking"
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label>Last 4 Digits</label>
                <input
                  type="text" maxLength="4"
                  value={formData.account_last4}
                  onChange={e => setFormData({ ...formData, account_last4: e.target.value })}
                  placeholder="1234"
                />
              </div>
              <div>
                <label>Account Type</label>
                <select
                  value={formData.account_type}
                  onChange={e => setFormData({ ...formData, account_type: e.target.value })}
                >
                  <option value="checking">Checking</option>
                  <option value="savings">Savings</option>
                  <option value="credit">Credit Card</option>
                </select>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
              <button type="button" onClick={onClose} className="btn-secondary" style={{ flex: 1 }}>Cancel</button>
              <button type="submit" disabled={loading} className="btn-primary" style={{ flex: 1 }}>
                {loading ? 'Creating...' : 'Create Account'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default AddAccountModal;
