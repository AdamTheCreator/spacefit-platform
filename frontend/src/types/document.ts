/**
 * Document types for the flyer parser and document management
 */

export type DocumentType =
  | 'leasing_flyer'
  | 'void_analysis'
  | 'investment_memo'
  | 'loan_document'
  | 'comp_report'
  | 'other';

export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface AvailableSpace {
  id: string;
  document_id: string;
  property_id: string | null;
  suite_number: string | null;
  building_address: string | null;
  square_footage: number | null;
  min_divisible_sf: number | null;
  max_contiguous_sf: number | null;
  asking_rent_psf: number | null;
  rent_type: string | null;
  is_endcap: boolean;
  is_anchor: boolean;
  has_drive_thru: boolean;
  has_patio: boolean;
  features: Record<string, unknown> | null;
  notes: string | null;
  previous_tenant: string | null;
  created_at: string;
}

export interface ExistingTenant {
  id: string;
  document_id: string;
  property_id: string | null;
  name: string;
  category: string | null;
  suite_number: string | null;
  square_footage: number | null;
  is_anchor: boolean;
  is_national: boolean;
  created_at: string;
}

export interface ParsedDocument {
  id: string;
  user_id: string;
  property_id: string | null;
  filename: string;
  file_size: number;
  mime_type: string;
  page_count: number | null;
  document_type: DocumentType;
  confidence_score: number | null;
  status: DocumentStatus;
  error_message: string | null;
  extracted_data: ExtractedData | null;
  created_at: string;
  processed_at: string | null;
}

export interface ParsedDocumentDetail extends ParsedDocument {
  available_spaces: AvailableSpace[];
  existing_tenants: ExistingTenant[];
}

export interface DocumentListResponse {
  items: ParsedDocument[];
  total: number;
  page: number;
  page_size: number;
}

export interface DocumentUploadResponse {
  id: string;
  filename: string;
  status: DocumentStatus;
  message: string;
}

// Extracted data structures
export interface ExtractedPropertyInfo {
  name: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  property_type: string | null;
  total_sf: number | null;
  year_built: number | null;
  parking_ratio: string | null;
  landlord_name: string | null;
}

export interface ExtractedAvailableSpace {
  suite_number: string | null;
  building_address: string | null;
  square_footage: number | null;
  min_divisible_sf: number | null;
  asking_rent_psf: number | null;
  rent_type: string | null;
  is_endcap: boolean;
  is_anchor: boolean;
  has_drive_thru: boolean;
  has_patio: boolean;
  previous_tenant: string | null;
  notes: string | null;
}

export interface ExtractedTenant {
  name: string;
  category: string | null;
  suite_number: string | null;
  square_footage: number | null;
  is_anchor: boolean;
  is_national: boolean;
}

export interface ExtractedFlyerData {
  property_info: ExtractedPropertyInfo;
  available_spaces: ExtractedAvailableSpace[];
  existing_tenants: ExtractedTenant[];
  amenities: string[];
  highlights: string[];
  contact_info: {
    broker_name: string | null;
    company: string | null;
    phone: string | null;
    email: string | null;
  } | null;
}

export interface VoidCategory {
  category_name: string;
  subcategory: string | null;
  is_void: boolean;
  site_count: number;
  market_count: number;
  avg_square_footage: number | null;
  existing_retailers: string[];
  void_opportunities: string[];
  match_score: number | null;
  common_cotenants: string[];
  notes: string | null;
}

export interface ExtractedVoidData {
  property_address: string | null;
  radius_miles: number | null;
  analysis_date: string | null;
  categories: VoidCategory[];
  summary: {
    total_categories_analyzed: number;
    total_voids: number;
    high_priority_voids: string[];
    key_insights: string[];
  };
}

export interface ExtractedInvestmentData {
  property_info: ExtractedPropertyInfo & {
    gla_sf: number | null;
    land_area_sf: number | null;
    status: string | null;
  };
  financials: {
    irr: number | null;
    rental_yield: number | null;
    exit_cap_rate: number | null;
    land_price: number | null;
    land_price_psf: number | null;
    total_investment: number | null;
    noi: number | null;
    asking_rent_psf: number | null;
    rent_type: string | null;
    cam_charges_psf: number | null;
  };
  demographics: {
    radius_miles: number | null;
    population: number | null;
    households: number | null;
    median_hh_income: number | null;
    avg_hh_income: number | null;
    daytime_employment: number | null;
    traffic_count: number | null;
  };
  tenant_interest: Array<{
    tenant_name: string;
    category: string | null;
    status: string | null;
    square_footage: number | null;
  }>;
  highlights: string[];
  scope_of_work: string | null;
  timing: {
    delivery_date: string | null;
    construction_start: string | null;
    lease_up_period: string | null;
  } | null;
}

// Union type for extracted data based on document type
export type ExtractedData = ExtractedFlyerData | ExtractedVoidData | ExtractedInvestmentData | Record<string, unknown>;
