import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { X, CheckCircle2, AlertCircle, Info, AlertTriangle } from 'lucide-react';

const NotificationContext = createContext(null);

export const useNotification = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotification must be used within a NotificationProvider');
  }
  return context;
};

export const NotificationProvider = ({ children }) => {
  const [notifications, setNotifications] = useState([]);

  const showNotification = useCallback((message, type = 'info', duration = 5000) => {
    const id = Math.random().toString(36).substring(2, 9);
    setNotifications((prev) => [...prev, { id, message, type, duration }]);
    
    if (duration !== Infinity) {
      setTimeout(() => {
        removeNotification(id);
      }, duration);
    }
    return id;
  }, []);

  const removeNotification = useCallback((id) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  return (
    <NotificationContext.Provider value={{ showNotification, removeNotification }}>
      {children}
      <NotificationContainer notifications={notifications} removeNotification={removeNotification} />
    </NotificationContext.Provider>
  );
};

const NotificationContainer = ({ notifications, removeNotification }) => {
  return (
    <div className="notification-container">
      {notifications.map((notification) => (
        <Toast
          key={notification.id}
          notification={notification}
          onClose={() => removeNotification(notification.id)}
        />
      ))}
      <style>{`
        .notification-container {
          position: fixed;
          top: 24px;
          right: 24px;
          z-index: 9999;
          display: flex;
          flex-direction: column;
          gap: 12px;
          pointer-events: none;
          max-width: 400px;
          width: calc(100% - 48px);
        }
        @media (max-width: 768px) {
          .notification-container {
            top: auto;
            bottom: 24px;
            right: 12px;
            left: 12px;
            width: auto;
          }
        }
      `}</style>
    </div>
  );
};

const Toast = ({ notification, onClose }) => {
  const { message, type } = notification;

  const getIcon = () => {
    switch (type) {
      case 'success': return <CheckCircle2 size={20} color="#C19B2E" />;
      case 'error': return <AlertCircle size={20} color="#ba1a1a" />;
      case 'warning': return <AlertTriangle size={20} color="#f59e0b" />;
      default: return <Info size={20} color="#111111" />;
    }
  };

  const getBorderColor = () => {
    switch (type) {
      case 'success': return 'var(--primary-gold)';
      case 'error': return '#ba1a1a';
      case 'warning': return '#f59e0b';
      default: return 'var(--bg-nav)';
    }
  };

  return (
    <div className="toast-item animate-toast-in">
      <div className="toast-content">
        <div className="toast-icon">{getIcon()}</div>
        <div className="toast-message">{message}</div>
        <button className="toast-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="toast-progress" style={{ backgroundColor: getBorderColor() }}></div>
      <style>{`
        .toast-item {
          background: white;
          border: 1px solid var(--border-light);
          pointer-events: auto;
          box-shadow: 0 10px 30px rgba(0,0,0,0.08);
          position: relative;
          overflow: hidden;
          animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        .toast-content {
          display: flex;
          align-items: flex-start;
          padding: 16px;
          gap: 12px;
        }
        .toast-icon {
          flex-shrink: 0;
          margin-top: 2px;
        }
        .toast-message {
          flex: 1;
          font-size: 14px;
          font-weight: 600;
          color: var(--text-main);
          line-height: 1.4;
          font-family: var(--font-body);
        }
        .toast-close {
          background: none;
          border: none;
          color: var(--text-muted);
          cursor: pointer;
          padding: 4px;
          margin-top: -4px;
          margin-right: -4px;
          transition: color 0.2s;
        }
        .toast-close:hover {
          color: var(--text-main);
        }
        .toast-progress {
          position: absolute;
          bottom: 0;
          left: 0;
          height: 3px;
          width: 100%;
          animation: progress linear forwards;
          animation-duration: ${notification.duration}ms;
        }
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        @keyframes progress {
          from { width: 100%; }
          to { width: 0%; }
        }
        .animate-toast-in {
          animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
      `}</style>
    </div>
  );
};
