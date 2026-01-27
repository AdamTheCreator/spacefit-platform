export interface SiteConfig {
  id: string;
  name: string;
  description: string;
  icon: string;
  url: string;
  data_types: string[];
  typical_duration_seconds: number;
  is_browser_based: boolean;
  coming_soon?: boolean;
  requires_manual_login?: boolean; // Site has CAPTCHA requiring manual browser login
}

export type SessionStatus = 'unknown' | 'valid' | 'expired' | 'error' | 'requires_manual_login';

export interface Credential {
  id: string;
  site_name: string;
  site_url: string;
  username: string;
  is_verified: boolean;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
  session_status: SessionStatus;
  session_last_checked: string | null;
  session_error_message: string | null;
  last_used_at: string | null;
  total_uses: number;
}

export interface CredentialCreate {
  site_name: string;
  site_url: string;
  username: string;
  password: string;
  additional_config?: Record<string, unknown>;
}

export interface CredentialUpdate {
  site_url?: string;
  username?: string;
  password?: string;
  additional_config?: Record<string, unknown>;
}

export interface VerifyResult {
  success: boolean;
  message: string;
}

// Connector health types
export type ConnectorStatus =
  | 'connected'
  | 'stale'
  | 'needs_reauth'
  | 'degraded'
  | 'error'
  | 'disabled';

export interface ConnectorStatusItem {
  credential_id: string;
  site_name: string;
  site_display_name: string;
  connector_status: ConnectorStatus;
  last_probe_at: string | null;
  last_used_at: string | null;
  session_error_message: string | null;
  requires_manual_login: boolean;
}

export interface ConnectorProbeResult {
  credential_id: string;
  connector_status: ConnectorStatus;
  probe_duration_ms: number;
  message: string;
}
