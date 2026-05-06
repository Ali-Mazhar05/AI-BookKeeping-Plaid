import React from 'react';
import { AlertTriangle, RefreshCcw } from 'lucide-react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary-container">
          <div className="premium-card" style={{ maxWidth: '600px', textAlign: 'center', padding: 'var(--spacing-xl)' }}>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 'var(--spacing-lg)' }}>
              <div style={{ width: '80px', height: '80px', borderRadius: '50%', background: 'rgba(186, 26, 26, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <AlertTriangle size={40} color="#ba1a1a" />
              </div>
            </div>
            <h2 style={{ fontSize: '32px', marginBottom: 'var(--spacing-md)' }}>System Interruption</h2>
            <p style={{ color: 'var(--text-muted)', marginBottom: 'var(--spacing-lg)', fontSize: '16px' }}>
              We encountered an unexpected error while processing your request. Our team has been notified.
            </p>
            <div style={{ background: '#f8f8f8', padding: 'var(--spacing-md)', borderRadius: '8px', marginBottom: 'var(--spacing-xl)', textAlign: 'left', fontSize: '13px', fontFamily: 'monospace', overflowX: 'auto', borderLeft: '4px solid #ba1a1a' }}>
              {this.state.error && this.state.error.toString()}
            </div>
            <button 
              className="btn-primary" 
              onClick={() => window.location.reload()}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              <RefreshCcw size={18} /> RELOAD APPLICATION
            </button>
          </div>
          <style>{`
            .error-boundary-container {
              display: flex;
              align-items: center;
              justify-content: center;
              min-height: 80vh;
              padding: var(--spacing-lg);
              animation: fadeIn 0.5s ease-out;
            }
          `}</style>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
