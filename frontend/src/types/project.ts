import type { Property } from './deal';
import type { ParsedDocument } from './document';

export interface ChatSessionBrief {
  id: string;
  title: string | null;
  analysis_type: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  user_id: string;
  property_id: string | null;
  name: string;
  description: string | null;
  instructions: string | null;
  is_archived: boolean;
  document_count: number;
  session_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail extends Project {
  property: Property | null;
  documents: ParsedDocument[];
  sessions: ChatSessionBrief[];
}

export interface ProjectListResponse {
  items: Project[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProjectCreate {
  name: string;
  property_id?: string;
  description?: string;
  instructions?: string;
}

export interface ProjectUpdate {
  name?: string;
  property_id?: string;
  description?: string;
  instructions?: string;
}
