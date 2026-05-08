import React, { useState, useEffect } from 'react';
import { X, Building2, RotateCcw, Plus, Trash2 } from 'lucide-react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useNotification } from './Notification';
import ConfirmModal from './ConfirmModal';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const AddPropertyModal = ({ entityId, onClose, onSuccess }) => {
  const navigate = useNavigate();
  const { showNotification } = useNotification();
  const [tab, setTab] = useState('new'); // 'new' | 'restore'
  const [loading, setLoading] = useState(false);
  const [inactiveProperties, setInactiveProperties] = useState([]);
  const [loadingInactive, setLoadingInactive] = useState(false);
  const [actionId, setActionId] = useState(null);
  const [formData, setFormData] = useState({ name: '', address: '', city: '', state: '', zip: '' });

  // Confirm dialog
  const [confirm, setConfirm] = useState({ isOpen: false });
  const closeConfirm = () => setConfirm({ isOpen: false });
  const openConfirm  = (opts) => setConfirm({ isOpen: true, ...opts });

  useEffect(() => {
    if (tab === 'restore') fetchInactive();
  }, [tab]);

  const fetchInactive = async () => {
    setLoadingInactive(true);
    try {
      const res = await axios.get(`${API_BASE}/meta/properties/inactive?entity_id=${entityId}`);
      setInactiveProperties(res.data.data);
    } catch {
      showNotification('Failed to load hidden properties.', 'error');
    } finally {
      setLoadingInactive(false);
    }
  };

  const set = (key) => (e) => setFormData({ ...formData, [key]: e.target.value });

  const handleCreate = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post(`${API_BASE}/meta/properties`, { ...formData, entity_id: entityId });
      showNotification('Property added successfully.', 'success');
      onSuccess();
      onClose();
    } catch (err) {
      showNotification(err.response?.data?.detail || 'Failed to create property', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleRestore = async (prop) => {
    setActionId(prop.id);
    try {
      await axios.post(`${API_BASE}/meta/properties/${prop.id}/restore`);
      showNotification(`"${prop.name}" restored to dashboard.`, 'success');
      onSuccess();
      onClose();
    } catch (err) {
      showNotification(err.response?.data?.detail || 'Failed to restore property', 'error');
    } finally {
      setActionId(null);
    }
  };

  const handleDelete = (prop) => {
    openConfirm({
      title:       'Delete Property Permanently',
      message:     `Permanently delete "${prop.name}" from the database? This cannot be undone.`,
      danger:      true,
      confirmText: 'Delete',
      onConfirm:   async () => {
        closeConfirm();
        setActionId(prop.id);
        try {
          await axios.delete(`${API_BASE}/meta/properties/${prop.id}/permanent`);
          showNotification(`"${prop.name}" permanently deleted.`, 'success');
          await fetchInactive();
          onSuccess();
        } catch (err) {
          showNotification(err.response?.data?.detail || 'Failed to delete property.', 'error');
        } finally {
          setActionId(null);
        }
      },
    });
  };

  const tabStyle = (active) => ({
    flex: 1, padding: '8px 0', fontSize: '12px', fontWeight: 700,
    letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer',
    border: 'none', background: 'none', transition: 'all 0.15s',
    borderBottom: active ? '2px solid var(--primary-gold)' : '2px solid transparent',
    color:         active ? 'var(--primary-gold)' : 'var(--text-muted)',
  });

  return (
    <>
      <div className="modal-overlay">
        <div className="premium-card modal-content" style={{ maxWidth: '520px', width: '92%', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}>

          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Building2 size={20} color="var(--primary-gold)" />
              <h2 style={{ fontSize: '20px', margin: 0 }}>Add Property</h2>
            </div>
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', lineHeight: 0 }}>
              <X size={20} />
            </button>
          </div>

          {/* Tabs */}
          <div style={{ display: 'flex', borderBottom: '1px solid var(--border-light)', marginBottom: '20px', flexShrink: 0 }}>
            <button style={tabStyle(tab === 'new')} onClick={() => setTab('new')}>
              <Plus size={12} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
              New Property
            </button>
            <button style={tabStyle(tab === 'restore')} onClick={() => setTab('restore')}>
              <RotateCcw size={12} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
              Hidden ({inactiveProperties.length || '…'})
            </button>
          </div>

          {/* New property form */}
          {tab === 'new' && (
            <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '14px', flexShrink: 0 }}>
              <div>
                <label>Property Name *</label>
                <input type="text" required value={formData.name} onChange={set('name')} placeholder="e.g. 123 Main St Rental" />
              </div>
              <div>
                <label>Street Address</label>
                <input type="text" value={formData.address} onChange={set('address')} placeholder="e.g. 123 Main Street" />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 80px 100px', gap: '10px' }}>
                <div>
                  <label>City</label>
                  <input type="text" value={formData.city} onChange={set('city')} placeholder="City" />
                </div>
                <div>
                  <label>State</label>
                  <input type="text" maxLength="2" value={formData.state} onChange={set('state')} placeholder="CA" style={{ textTransform: 'uppercase' }} />
                </div>
                <div>
                  <label>ZIP</label>
                  <input type="text" maxLength="10" value={formData.zip} onChange={set('zip')} placeholder="90210" />
                </div>
              </div>
              <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
                <button type="button" onClick={onClose} className="btn-secondary" style={{ flex: 1 }}>Cancel</button>
                <button type="submit" disabled={loading} className="btn-primary" style={{ flex: 1 }}>
                  {loading ? 'Creating…' : 'Add Property'}
                </button>
              </div>
            </form>
          )}

          {/* Restore / delete hidden properties */}
          {tab === 'restore' && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
              {loadingInactive ? (
                <div style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)', fontSize: '13px' }}>
                  Loading hidden properties…
                </div>
              ) : inactiveProperties.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)', fontSize: '13px' }}>
                  No hidden properties found.<br />
                  <span style={{ fontSize: '12px' }}>Properties removed from the dashboard appear here.</span>
                </div>
              ) : (
                <>
                  <p style={{ margin: '0 0 12px', fontSize: '12px', color: 'var(--text-muted)', flexShrink: 0 }}>
                    Delete is enabled only when no transactions are allocated to the property.
                  </p>
                  <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {inactiveProperties.map(prop => {
                      const busy    = actionId === prop.id;
                      const canDel  = prop.tx_count === 0;
                      const delTip  = canDel
                        ? 'Permanently delete'
                        : `${prop.tx_count} allocation${prop.tx_count !== 1 ? 's' : ''} still assigned — reassign first`;

                      return (
                        <div
                          key={prop.id}
                          style={{
                            display: 'flex', alignItems: 'center',
                            padding: '12px 14px',
                            border: '1px solid var(--border-light)',
                            borderRadius: '4px',
                            gap: '12px',
                          }}
                        >
                          {/* Property info */}
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontWeight: 700, fontSize: '13px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {prop.name}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px', flexWrap: 'wrap' }}>
                              {(prop.city || prop.state) && (
                                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                                  {[prop.city, prop.state].filter(Boolean).join(', ')}
                                </span>
                              )}
                              {prop.tx_count > 0 && (
                                <span style={{
                                  fontSize: '10px', fontWeight: 700, padding: '1px 6px',
                                  background: 'rgba(186,26,26,0.08)', color: '#ba1a1a', borderRadius: '10px',
                                }}>
                                  {prop.tx_count} allocation{prop.tx_count !== 1 ? 's' : ''}
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Actions */}
                          <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                            <button
                              className="btn-primary"
                              disabled={busy}
                              onClick={() => handleRestore(prop)}
                              style={{ fontSize: '11px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '4px' }}
                            >
                              <RotateCcw size={12} />
                              {busy && actionId === prop.id ? 'Restoring…' : 'Restore'}
                            </button>

                            {prop.tx_count > 0 ? (
                              <button
                                onClick={() => { onClose(); navigate(`/transactions?property_id=${prop.id}`); }}
                                title={delTip}
                                style={{
                                  fontSize: '11px', padding: '6px 10px',
                                  display: 'flex', alignItems: 'center', gap: '4px',
                                  border: '1px solid var(--border-light)',
                                  background: 'transparent', color: 'var(--text-muted)',
                                  cursor: 'pointer',
                                }}
                              >
                                <Trash2 size={12} />
                                {prop.tx_count} tx
                              </button>
                            ) : (
                              <button
                                disabled={busy}
                                onClick={() => !busy && handleDelete(prop)}
                                title={delTip}
                                style={{
                                  fontSize: '11px', padding: '6px 10px',
                                  display: 'flex', alignItems: 'center', gap: '4px',
                                  border: '1px solid rgba(186,26,26,0.35)',
                                  background: 'rgba(186,26,26,0.06)', color: '#ba1a1a',
                                  cursor: busy ? 'not-allowed' : 'pointer',
                                  opacity: busy ? 0.5 : 1,
                                }}
                              >
                                <Trash2 size={12} />
                                {busy ? '…' : 'Delete'}
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
              <div style={{ marginTop: '14px', flexShrink: 0 }}>
                <button onClick={onClose} className="btn-secondary" style={{ width: '100%' }}>Close</button>
              </div>
            </div>
          )}
        </div>
      </div>

      <ConfirmModal
        isOpen={confirm.isOpen}
        title={confirm.title}
        message={confirm.message}
        confirmText={confirm.confirmText || 'Confirm'}
        cancelText="Cancel"
        danger={confirm.danger}
        onConfirm={confirm.onConfirm}
        onCancel={closeConfirm}
      />
    </>
  );
};

export default AddPropertyModal;
