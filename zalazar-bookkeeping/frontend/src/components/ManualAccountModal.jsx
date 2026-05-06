import React, { useState } from 'react';
import axios from 'axios';
import { X } from 'lucide-react';
import { useNotification } from './Notification';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const ManualAccountModal = ({ entityId, onClose, onSuccess }) => {
  const { showNotification } = useNotification();
  const [formData, setFormData] = useState({
    bank_name: '',
    account_name: '',
    account_last4: '',
    account_type: 'checking'
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await axios.post(`${API_BASE}/bank-accounts/manual`, {
        ...formData,
        entity_id: entityId
      });
      onSuccess();
      showNotification("Bank account created successfully.", "success");
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create account');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="premium-card modal-content" style={{ maxWidth: '500px', width: '90%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--spacing-lg)' }}>
          <h2 style={{ fontSize: '20px' }}>Add Manual Account</h2>
          <X onClick={onClose} style={{ cursor: 'pointer' }} />
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
          <div>
            <label>Bank Name</label>
            <input 
              type="text" 
              required 
              value={formData.bank_name}
              onChange={e => setFormData({...formData, bank_name: e.target.value})}
              placeholder="e.g. Chase, Wells Fargo"
            />
          </div>
          <div>
            <label>Account Name</label>
            <input 
              type="text" 
              required 
              value={formData.account_name}
              onChange={e => setFormData({...formData, account_name: e.target.value})}
              placeholder="e.g. Business Checking"
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-md)' }}>
            <div>
              <label>Last 4 Digits</label>
              <input 
                type="text" 
                maxLength="4"
                value={formData.account_last4}
                onChange={e => setFormData({...formData, account_last4: e.target.value})}
                placeholder="1234"
              />
            </div>
            <div>
              <label>Type</label>
              <select 
                value={formData.account_type}
                onChange={e => setFormData({...formData, account_type: e.target.value})}
              >
                <option value="checking">Checking</option>
                <option value="savings">Savings</option>
                <option value="credit">Credit Card</option>
              </select>
            </div>
          </div>

          {error && <div style={{ color: '#ba1a1a', fontSize: '12px' }}>{error}</div>}

          <div style={{ display: 'flex', gap: 'var(--spacing-md)', marginTop: 'var(--spacing-lg)' }}>
            <button type="button" onClick={onClose} className="btn-secondary" style={{ flex: 1 }}>Cancel</button>
            <button type="submit" disabled={loading} className="btn-primary" style={{ flex: 1 }}>
              {loading ? 'Creating...' : 'Create Account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ManualAccountModal;
