import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Tag, Plus, EyeOff, Trash2, AlertTriangle } from 'lucide-react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useNotification } from './Notification';
import ConfirmModal from './ConfirmModal';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const ACCOUNT_TYPES = [
  { value: 'income',               label: 'Income' },
  { value: 'operating_expense',    label: 'Operating Expense' },
  { value: 'property_cost',        label: 'Property Cost' },
  { value: 'capital_non_expense',  label: 'Capital / Non-Expense' },
  { value: 'transfer',             label: 'Transfer' },
  { value: 'other',                label: 'Other' },
];

const TYPE_COLOR = {
  income:               '#1e7e34',
  operating_expense:    '#ba1a1a',
  property_cost:        '#c19b2e',
  capital_non_expense:  '#2563eb',
  transfer:             '#6b7280',
  other:                '#6b7280',
};

const ManageCategoriesModal = ({ onClose, onSuccess }) => {
  const navigate    = useNavigate();
  const { showNotification } = useNotification();

  const [tab, setTab]                     = useState('active'); // 'active' | 'hidden' | 'create'
  const [activeCategories, setActive]     = useState([]);
  const [hiddenCategories, setHidden]     = useState([]);
  const [loading, setLoading]             = useState(true);
  const [actionId, setActionId]           = useState(null); // id of row being acted on

  // Create-category form
  const [form, setForm] = useState({ code: '', name: '', account_type: '', is_pnl: true });
  const [creating, setCreating] = useState(false);

  // Confirm dialog
  const [confirm, setConfirm] = useState({ isOpen: false });
  const closeConfirm = () => setConfirm({ isOpen: false });
  const openConfirm  = (opts) => setConfirm({ isOpen: true, ...opts });

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [a, h] = await Promise.all([
        axios.get(`${API_BASE}/meta/accounts`),
        axios.get(`${API_BASE}/meta/accounts/inactive`),
      ]);
      setActive(a.data.data);
      setHidden(h.data.data);
    } catch {
      showNotification('Failed to load categories.', 'error');
    } finally {
      setLoading(false);
    }
  };

  // ── Hide (set is_assignable = FALSE) ──────────────────────────────────────
  const handleHide = (cat) => {
    if (cat.tx_count > 0) {
      openConfirm({
        title:   'Category In Use',
        message: `"${cat.code} – ${cat.name}" is assigned to ${cat.tx_count} transaction${cat.tx_count !== 1 ? 's' : ''}. Reassign them to a different category before hiding this one.`,
        warning: true,
        confirmText:  'OK',
        secondaryAction: {
          label:   `View ${cat.tx_count} Transaction${cat.tx_count !== 1 ? 's' : ''}`,
          onClick: () => { closeConfirm(); onClose(); navigate(`/transactions?category_id=${cat.id}`); },
        },
        onConfirm: closeConfirm,
      });
      return;
    }
    openConfirm({
      title:       'Hide Category',
      message:     `Hide "${cat.code} – ${cat.name}"? It won't appear in transaction dropdowns but can be restored any time.`,
      warning:     true,
      confirmText: 'Hide',
      onConfirm:   async () => {
        closeConfirm();
        setActionId(cat.id);
        try {
          await axios.patch(`${API_BASE}/meta/accounts/${cat.id}/assignable`);
          showNotification(`"${cat.name}" hidden.`, 'success');
          await fetchAll();
          onSuccess?.();
        } catch { showNotification('Failed to hide category.', 'error'); }
        finally  { setActionId(null); }
      },
    });
  };

  // ── Add back (set is_assignable = TRUE) ───────────────────────────────────
  const handleAdd = async (cat) => {
    setActionId(cat.id);
    try {
      await axios.patch(`${API_BASE}/meta/accounts/${cat.id}/assignable`);
      showNotification(`"${cat.name}" added to categories.`, 'success');
      await fetchAll();
      onSuccess?.();
    } catch { showNotification('Failed to enable category.', 'error'); }
    finally  { setActionId(null); }
  };

  // ── Permanent delete ───────────────────────────────────────────────────────
  const handleDelete = (cat) => {
    openConfirm({
      title:       'Delete Category Permanently',
      message:     `Permanently delete "${cat.code} – ${cat.name}" from the database? This cannot be undone.`,
      danger:      true,
      confirmText: 'Delete',
      onConfirm:   async () => {
        closeConfirm();
        setActionId(cat.id);
        try {
          await axios.delete(`${API_BASE}/meta/accounts/${cat.id}`);
          showNotification(`"${cat.name}" permanently deleted.`, 'success');
          await fetchAll();
          onSuccess?.();
        } catch (err) {
          showNotification(err.response?.data?.detail || 'Failed to delete category.', 'error');
        } finally { setActionId(null); }
      },
    });
  };

  // ── Create new category ───────────────────────────────────────────────────
  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.code.trim() || !form.name.trim() || !form.account_type) {
      showNotification('Code, Name, and Type are required.', 'warning');
      return;
    }
    setCreating(true);
    try {
      await axios.post(`${API_BASE}/meta/accounts`, {
        code:         form.code.trim(),
        name:         form.name.trim(),
        account_type: form.account_type,
        is_pnl:       form.is_pnl,
      });
      showNotification(`Category "${form.name}" created.`, 'success');
      setForm({ code: '', name: '', account_type: '', is_pnl: true });
      await fetchAll();
      onSuccess?.();
      setTab('active');
    } catch (err) {
      showNotification(err.response?.data?.detail || 'Failed to create category.', 'error');
    } finally { setCreating(false); }
  };

  // ── Styles ────────────────────────────────────────────────────────────────
  const tabStyle = (active) => ({
    flex: 1, padding: '8px 0', fontSize: '12px', fontWeight: 700,
    letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer',
    border: 'none', background: 'none', transition: 'all 0.15s',
    borderBottom: active ? '2px solid var(--primary-gold)' : '2px solid transparent',
    color:         active ? 'var(--primary-gold)' : 'var(--text-muted)',
  });

  // ── Row renderer ──────────────────────────────────────────────────────────
  const renderRow = (cat, isActive) => {
    const busy    = actionId === cat.id;
    const canDel  = cat.tx_count === 0;
    const delTip  = canDel ? 'Permanently delete' : `${cat.tx_count} transaction${cat.tx_count !== 1 ? 's' : ''} assigned — reassign first`;

    return (
      <div
        key={cat.id}
        style={{
          display: 'flex', alignItems: 'center', gap: '10px',
          padding: '10px 14px', borderBottom: '1px solid var(--border-light)',
        }}
      >
        {/* Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, fontSize: '13px', fontFamily: 'var(--font-headline)', flexShrink: 0 }}>
              {cat.code}
            </span>
            <span style={{ fontSize: '13px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {cat.name}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px', flexWrap: 'wrap' }}>
            {cat.account_type && (
              <span style={{
                fontSize: '10px', fontWeight: 800, letterSpacing: '0.06em',
                color: TYPE_COLOR[cat.account_type] || '#6b7280', textTransform: 'uppercase',
              }}>
                {cat.account_type.replace(/_/g, ' ')}
              </span>
            )}
            {cat.tx_count > 0 && (
              <span style={{
                fontSize: '10px', fontWeight: 700, padding: '1px 6px',
                background: 'rgba(186,26,26,0.08)', color: '#ba1a1a', borderRadius: '10px',
              }}>
                {cat.tx_count} tx
              </span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
          {isActive ? (
            <button
              className="btn-secondary"
              disabled={busy}
              onClick={() => handleHide(cat)}
              title="Hide from dropdowns"
              style={{ fontSize: '11px', padding: '5px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <EyeOff size={12} />
              {busy ? '…' : 'Hide'}
            </button>
          ) : (
            <button
              className="btn-primary"
              disabled={busy}
              onClick={() => handleAdd(cat)}
              title="Re-enable in dropdowns"
              style={{ fontSize: '11px', padding: '5px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Plus size={12} />
              {busy ? '…' : 'Add'}
            </button>
          )}

          <button
            disabled={!canDel || busy}
            onClick={() => canDel && !busy && handleDelete(cat)}
            title={delTip}
            style={{
              fontSize: '11px', padding: '5px 10px',
              display: 'flex', alignItems: 'center', gap: '4px',
              border: '1px solid',
              borderColor:      canDel ? 'rgba(186,26,26,0.35)' : 'var(--border-light)',
              background:       canDel ? 'rgba(186,26,26,0.06)'  : 'transparent',
              color:            canDel ? '#ba1a1a'                : 'var(--text-muted)',
              cursor:           canDel ? 'pointer'                : 'not-allowed',
              opacity:          canDel ? 1                        : 0.45,
              transition:       'all 0.15s',
            }}
          >
            <Trash2 size={12} />
            {busy ? '…' : 'Delete'}
          </button>
        </div>
      </div>
    );
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return createPortal(
    <>
      <div className="modal-overlay" style={{ zIndex: 2500 }}>
        <div
          className="premium-card modal-content"
          style={{ maxWidth: '580px', width: '92%', padding: '24px', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}
        >
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Tag size={20} color="var(--primary-gold)" />
              <h2 style={{ fontSize: '20px', margin: 0 }}>Manage Categories</h2>
            </div>
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', lineHeight: 0 }}>
              <X size={20} />
            </button>
          </div>

          <p style={{ margin: '0 0 14px', fontSize: '12px', color: 'var(--text-muted)', flexShrink: 0 }}>
            Active categories appear in transaction dropdowns. Delete is enabled only when no transactions are assigned.
          </p>

          {/* Tabs */}
          <div style={{ display: 'flex', borderBottom: '1px solid var(--border-light)', marginBottom: '12px', flexShrink: 0 }}>
            <button style={tabStyle(tab === 'active')} onClick={() => setTab('active')}>
              Active ({activeCategories.length})
            </button>
            <button style={tabStyle(tab === 'hidden')} onClick={() => setTab('hidden')}>
              Hidden ({hiddenCategories.length})
            </button>
            <button style={tabStyle(tab === 'create')} onClick={() => setTab('create')}>
              <Plus size={11} style={{ marginRight: '3px', verticalAlign: 'middle' }} />
              Create
            </button>
          </div>

          {/* Content */}
          <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
            {/* ── Active / Hidden lists ─────────────────────────────── */}
            {(tab === 'active' || tab === 'hidden') && (
              loading ? (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)', fontSize: '13px' }}>
                  Loading categories…
                </div>
              ) : tab === 'active' ? (
                activeCategories.length === 0
                  ? <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)', fontSize: '13px' }}>No active categories.</div>
                  : activeCategories.map(cat => renderRow(cat, true))
              ) : (
                hiddenCategories.length === 0
                  ? (
                    <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)', fontSize: '13px' }}>
                      No hidden categories.<br />
                      <span style={{ fontSize: '12px' }}>Categories you hide will appear here.</span>
                    </div>
                  )
                  : hiddenCategories.map(cat => renderRow(cat, false))
              )
            )}

            {/* ── Create form ───────────────────────────────────────── */}
            {tab === 'create' && (
              <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '14px', padding: '4px 0' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '12px' }}>
                  <div>
                    <label>Code *</label>
                    <input
                      type="text" required
                      value={form.code}
                      onChange={(e) => setForm(f => ({ ...f, code: e.target.value }))}
                      placeholder="e.g. 5050"
                      style={{ fontFamily: 'var(--font-headline)', letterSpacing: '0.05em' }}
                    />
                  </div>
                  <div>
                    <label>Category Name *</label>
                    <input
                      type="text" required
                      value={form.name}
                      onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))}
                      placeholder="e.g. Landscaping"
                    />
                  </div>
                </div>

                <div>
                  <label>Account Type *</label>
                  <select
                    required
                    value={form.account_type}
                    onChange={(e) => setForm(f => ({ ...f, account_type: e.target.value }))}
                    className="form-select"
                  >
                    <option value="">Select type…</option>
                    {ACCOUNT_TYPES.map(t => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <input
                    type="checkbox"
                    id="is-pnl"
                    checked={form.is_pnl}
                    onChange={(e) => setForm(f => ({ ...f, is_pnl: e.target.checked }))}
                    style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                  />
                  <label htmlFor="is-pnl" style={{ cursor: 'pointer', margin: 0, fontSize: '13px', fontWeight: 600 }}>
                    Affects Profit & Loss statement
                  </label>
                </div>

                <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
                  <button
                    type="button"
                    onClick={() => setTab('active')}
                    className="btn-secondary"
                    style={{ flex: 1 }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={creating}
                    className="btn-primary"
                    style={{ flex: 2 }}
                  >
                    {creating ? 'Creating…' : 'Create Category'}
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* Footer hint */}
          {tab !== 'create' && (
            <div style={{ marginTop: '14px', flexShrink: 0, borderTop: '1px solid var(--border-light)', paddingTop: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
                <AlertTriangle size={12} color="#f59e0b" />
                Delete is disabled while transactions are assigned — reassign them first, then delete.
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
        warning={confirm.warning}
        secondaryAction={confirm.secondaryAction}
        onConfirm={confirm.onConfirm}
        onCancel={closeConfirm}
      />
    </>,
    document.body
  );
};

export default ManageCategoriesModal;
