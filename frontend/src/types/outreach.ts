/**
 * Outreach Campaign Types
 *
 * Types for email outreach campaigns based on void analysis.
 */

export type CampaignStatus = 'draft' | 'scheduled' | 'sending' | 'sent' | 'cancelled';
export type RecipientStatus =
  | 'pending'
  | 'sent'
  | 'delivered'
  | 'opened'
  | 'clicked'
  | 'replied'
  | 'bounced'
  | 'unsubscribed';

export interface OutreachRecipient {
  id: string;
  tenant_name: string;
  contact_email: string;
  contact_name: string | null;
  category: string | null;
  match_score: number | null;
  nearest_location: string | null;
  distance_miles: number | null;
  status: RecipientStatus;
  is_excluded: boolean;
  sent_at: string | null;
  opened_at: string | null;
  clicked_at: string | null;
  replied_at: string | null;
}

export interface OutreachCampaign {
  id: string;
  name: string;
  property_address: string;
  property_name: string | null;
  subject: string;
  body_template: string;
  from_name: string;
  from_email: string;
  reply_to: string | null;
  status: CampaignStatus;
  created_at: string;
  sent_at: string | null;
  total_recipients: number;
  sent_count: number;
  opened_count: number;
  clicked_count: number;
  replied_count: number;
  bounced_count: number;
  recipients?: OutreachRecipient[];
}

export interface OutreachCampaignListItem {
  id: string;
  name: string;
  property_name: string | null;
  status: CampaignStatus;
  created_at: string;
  sent_at: string | null;
  total_recipients: number;
  sent_count: number;
  opened_count: number;
  replied_count: number;
}

export interface OutreachTemplate {
  id: string;
  name: string;
  description: string | null;
  subject_template: string;
  body_template: string;
  category: string | null;
  times_used: number;
  is_default: boolean;
}

export interface CreateCampaignRequest {
  name: string;
  property_address: string;
  property_name?: string;
  subject: string;
  body_template: string;
  from_name: string;
  from_email: string;
  reply_to?: string;
  recipients: CreateRecipientRequest[];
}

export interface CreateRecipientRequest {
  tenant_name: string;
  contact_email: string;
  contact_name?: string;
  contact_title?: string;
  category?: string;
  match_score?: number;
  nearest_location?: string;
  distance_miles?: number;
}

export interface SendCampaignResponse {
  success: boolean;
  message: string;
  total_sent: number;
  total_failed: number;
}
