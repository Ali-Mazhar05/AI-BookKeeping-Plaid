import React, { useState, useEffect, useCallback } from 'react';
import { usePlaidLink } from 'react-plaid-link';
import axios from 'axios';
import { Link2 } from 'lucide-react';
import { useNotification } from './Notification';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const PlaidLinkButton = ({ entityId, accountId, onLinkSuccess, label, className = "btn-primary" }) => {
  const [linkToken, setLinkToken] = useState(null);
  const { showNotification } = useNotification();

  const generateToken = useCallback(async () => {
    if (!entityId) return;
    try {
      const payload = { entity_id: entityId };
      if (accountId) payload.account_id = accountId;
      
      const response = await axios.post(`${API_BASE}/plaid/link-token`, payload);
      setLinkToken(response.data.link_token);
    } catch (err) {
      console.error("Error generating link token", err);
    }
  }, [entityId, accountId]);

  useEffect(() => {
    generateToken();
  }, [generateToken]);

  const onSuccess = useCallback(async (public_token, metadata) => {
    try {
      // In update mode, we don't necessarily need to exchange if we already have the token,
      // but Plaid usually returns a success and we might want to refresh metadata.
      const response = await axios.post(`${API_BASE}/plaid/exchange-token`, {
        public_token,
        metadata,
        entity_id: entityId
      });
      if (onLinkSuccess) onLinkSuccess(response.data);
      showNotification(accountId ? "Connection fixed successfully!" : "Bank account connected successfully!", "success");
    } catch (err) {
      console.error("Error exchanging token", err);
      const detail = err.response?.data?.detail || err.message;
      showNotification(`Failed to complete Plaid action: ${detail}`, "error");
    }
  }, [entityId, onLinkSuccess, accountId]);


  const config = {
    token: linkToken,
    onSuccess,
  };

  const { open, ready } = usePlaidLink(config);

  return (
    <button 
      onClick={() => open()} 
      disabled={!ready}
      className={className}
    >
      <Link2 size={18} color="var(--primary-gold)" />
      {ready ? (label || "CONNECT BANK") : "LOADING..."}
    </button>
  );
};

export default PlaidLinkButton;
