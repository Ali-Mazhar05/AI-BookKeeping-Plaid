import React from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle, AlertCircle, X } from 'lucide-react';

/**
 * UI-friendly confirmation dialog — replaces all window.confirm / alert calls.
 *
 * Props:
 *   isOpen          boolean   — controls visibility
 *   title           string    — modal heading
 *   message         string    — body text
 *   confirmText     string    — confirm button label (default "Confirm")
 *   cancelText      string    — cancel button label (default "Cancel")
 *   onConfirm       fn        — called when user clicks confirm
 *   onCancel        fn        — called when user clicks cancel or X
 *   danger          boolean   — red confirm button + danger icon
 *   warning         boolean   — amber warning icon (non-destructive)
 *   secondaryAction { label, onClick } — optional third button (e.g. "View Transactions")
 */
const ConfirmModal = ({
  isOpen,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  onConfirm,
  onCancel,
  danger = false,
  warning = false,
  secondaryAction = null,
}) => {
  if (!isOpen) return null;

  const showIcon = danger || warning;

  return createPortal(
    <div
      className="modal-overlay"
      style={{ zIndex: 3000 }}
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div
        className="premium-card modal-content"
        style={{ maxWidth: '440px', width: '90%', padding: '28px 28px 24px' }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', marginBottom: '20px' }}>
          {showIcon && (
            <div style={{
              width: '42px', height: '42px', borderRadius: '50%', flexShrink: 0,
              background: danger ? 'rgba(186,26,26,0.1)' : 'rgba(245,158,11,0.1)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {danger
                ? <AlertCircle size={20} color="#ba1a1a" />
                : <AlertTriangle size={20} color="#f59e0b" />
              }
            </div>
          )}
          <div style={{ flex: 1 }}>
            <h3 style={{ margin: '0 0 6px', fontSize: '18px', fontFamily: 'var(--font-headline)', fontWeight: 700 }}>
              {title}
            </h3>
            <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.55' }}>
              {message}
            </p>
          </div>
          <button
            onClick={onCancel}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px', color: 'var(--text-muted)', flexShrink: 0, lineHeight: 0 }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          {secondaryAction && (
            <button
              onClick={secondaryAction.onClick}
              className="btn-secondary"
              style={{ fontSize: '12px', padding: '8px 14px', marginRight: 'auto' }}
            >
              {secondaryAction.label}
            </button>
          )}
          <button
            className="btn-secondary"
            onClick={onCancel}
            style={{ fontSize: '12px', padding: '8px 16px' }}
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            style={{
              fontSize: '12px', padding: '8px 16px',
              fontFamily: 'var(--font-body)', fontWeight: 700,
              letterSpacing: '0.05em', cursor: 'pointer', border: 'none',
              background: danger ? '#ba1a1a' : 'var(--bg-nav)',
              color: '#fff',
            }}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default ConfirmModal;
