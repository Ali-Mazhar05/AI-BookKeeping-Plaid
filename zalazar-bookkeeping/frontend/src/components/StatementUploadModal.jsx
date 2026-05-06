import React, { useState } from 'react';
import axios from 'axios';
import { X, Upload, FileText } from 'lucide-react';
import { useNotification } from './Notification';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const StatementUploadModal = ({ account, onClose, onSuccess }) => {
  const { showNotification } = useNotification();
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && (dropped.name.endsWith('.pdf') || dropped.name.endsWith('.csv'))) {
      setFile(dropped);
      setError('');
    } else if (dropped) {
      setError('Only PDF and CSV files are supported.');
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setError('');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const url = account.id 
        ? `${API_BASE}/bank-accounts/${account.id}/upload-statement` 
        : `${API_BASE}/bank-accounts/upload-global`;
        
      await axios.post(url, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setProgress(percentCompleted);
        }
      });
      onSuccess();
      showNotification("Statement uploaded and processing started.", "success");
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="premium-card modal-content" style={{ maxWidth: '450px', width: '90%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--spacing-lg)' }}>
          <div>
            <h2 style={{ fontSize: '20px' }}>Upload Statement</h2>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{account.bank_name} • {account.account_name}</p>
          </div>
          <X onClick={onClose} style={{ cursor: 'pointer' }} />
        </div>

        <form onSubmit={handleUpload}>
          <div
            style={{
              border: `2px dashed ${isDragging ? 'var(--primary-gold)' : 'var(--border-light)'}`,
              borderRadius: 'var(--radius-md)',
              padding: 'var(--spacing-xl)',
              textAlign: 'center',
              background: isDragging ? 'rgba(193,155,46,0.06)' : file ? 'var(--bg-panel)' : 'transparent',
              cursor: 'pointer',
              marginBottom: 'var(--spacing-lg)',
              transition: 'border-color 0.2s, background 0.2s'
            }}
            onClick={() => document.getElementById('fileInput').click()}
            onDragOver={handleDragOver}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <input 
              id="fileInput"
              type="file" 
              style={{ display: 'none' }} 
              accept=".pdf,.csv"
              onChange={e => setFile(e.target.files[0])}
            />
            {file ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                <FileText size={40} color="var(--primary-gold)" />
                <span style={{ fontWeight: 600 }}>{file.name}</span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{(file.size / 1024).toFixed(1)} KB</span>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                <Upload size={40} color="var(--border-light)" />
                <p style={{ fontWeight: 600 }}>Click or drag file to upload</p>
                <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Supports PDF and CSV bank statements</p>
              </div>
            )}
          </div>

          {loading && (
            <div style={{ width: '100%', height: '4px', background: 'var(--bg-panel)', marginBottom: 'var(--spacing-md)' }}>
              <div style={{ width: `${progress}%`, height: '100%', background: 'var(--primary-gold)', transition: 'width 0.3s' }}></div>
            </div>
          )}

          {error && <div style={{ color: '#ba1a1a', fontSize: '12px', marginBottom: 'var(--spacing-md)' }}>{error}</div>}

          <div style={{ display: 'flex', gap: 'var(--spacing-md)' }}>
            <button type="button" onClick={onClose} className="btn-secondary" style={{ flex: 1 }}>Cancel</button>
            <button type="submit" disabled={!file || loading} className="btn-primary" style={{ flex: 1 }}>
              {loading ? 'Processing...' : 'Upload & Process'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default StatementUploadModal;
