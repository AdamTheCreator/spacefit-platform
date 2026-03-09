export type DealStage = 'intake' | 'qualification' | 'due_diligence' | 'tenant_vetting' | 'loi' | 'under_contract' | 'closed' | 'passed' | 'dead';
export type DealType = 'lease' | 'sale' | 'sublease';
export type ActivityType = 'note' | 'call' | 'email' | 'meeting' | 'tour' | 'document';

export interface Property {
  id: string;
  name: string;
  address: string;
  city: string;
  state: string;
  zip_code: string;
  latitude?: number;
  longitude?: number;
  property_type: string;
  total_sf?: number;
  available_sf?: number;
  landlord_id?: string;
  notes?: string;

  // Market classification
  market_region?: string;
  metro_area?: string;
  product_type?: string;

  // Qualification
  intersection_quality?: string;
  traffic_count_vpd?: number;
  population_1mi?: number;
  population_3mi?: number;
  population_5mi?: number;
  median_hhi_3mi?: number;
  qualification_score?: number;
  qualification_data?: Record<string, unknown>;

  // Ownership & Zoning
  owner_name?: string;
  owner_entity?: string;
  zoning_code?: string;
  zoning_description?: string;

  // Pricing (for comps)
  asking_price?: number;
  cap_rate?: number;
  price_psf?: number;
  noi?: number;
  is_sale_comp: boolean;

  // Broker contact
  broker_name?: string;
  broker_company?: string;
  broker_phone?: string;
  broker_email?: string;

  // Source tracking
  source_type?: string;
  source_url?: string;

  created_at: string;
  updated_at: string;
}

export interface PropertyCreate {
  name: string;
  address: string;
  city: string;
  state: string;
  zip_code: string;
  latitude?: number;
  longitude?: number;
  property_type?: string;
  total_sf?: number;
  available_sf?: number;
  landlord_id?: string;
  notes?: string;
  market_region?: string;
  metro_area?: string;
  product_type?: string;
  intersection_quality?: string;
  traffic_count_vpd?: number;
  population_1mi?: number;
  population_3mi?: number;
  population_5mi?: number;
  median_hhi_3mi?: number;
  owner_name?: string;
  owner_entity?: string;
  zoning_code?: string;
  zoning_description?: string;
  asking_price?: number;
  cap_rate?: number;
  price_psf?: number;
  noi?: number;
  is_sale_comp?: boolean;
  broker_name?: string;
  broker_company?: string;
  broker_phone?: string;
  broker_email?: string;
  source_type?: string;
  source_url?: string;
}

export interface DealActivity {
  id: string;
  deal_id: string;
  user_id: string;
  activity_type: ActivityType;
  title: string;
  description?: string;
  scheduled_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface DealActivityCreate {
  activity_type: ActivityType;
  title: string;
  description?: string;
  scheduled_at?: string;
  completed_at?: string;
}

export interface DealStageHistory {
  id: string;
  deal_id: string;
  from_stage?: DealStage;
  to_stage: DealStage;
  changed_by: string;
  changed_at: string;
  notes?: string;
}

export interface Deal {
  id: string;
  user_id: string;
  name: string;
  stage: DealStage;
  deal_type: DealType;
  property_id?: string;
  customer_id?: string;
  asking_rent_psf?: number;
  negotiated_rent_psf?: number;
  square_footage?: number;
  commission_rate?: number;
  commission_amount?: number;
  probability: number;
  expected_close_date?: string;
  actual_close_date?: string;
  lease_start_date?: string;
  lease_term_months?: number;
  source?: string;
  notes?: string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  property?: Property;
  customer_name?: string;
}

export interface DealDetail extends Deal {
  stage_history: DealStageHistory[];
  activities: DealActivity[];
}

export interface DealCreate {
  name: string;
  stage?: DealStage;
  deal_type?: DealType;
  property_id?: string;
  customer_id?: string;
  asking_rent_psf?: number;
  negotiated_rent_psf?: number;
  square_footage?: number;
  commission_rate?: number;
  commission_amount?: number;
  probability?: number;
  expected_close_date?: string;
  actual_close_date?: string;
  lease_start_date?: string;
  lease_term_months?: number;
  source?: string;
  notes?: string;
}

export interface DealUpdate extends Partial<DealCreate> {
  is_archived?: boolean;
}

export interface DealStageUpdate {
  stage: DealStage;
  notes?: string;
}

export interface DealListResponse {
  items: Deal[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface StageSummary {
  stage: DealStage;
  count: number;
  total_commission: number;
}

export interface PipelineSummary {
  stages: StageSummary[];
  total_deals: number;
  total_potential_commission: number;
}

export interface MonthlyForecast {
  month: string;
  expected_commission: number;
  deal_count: number;
}

export interface CommissionForecast {
  forecast: MonthlyForecast[];
  total_forecast: number;
}

export interface DealCalendarItem {
  id: string;
  name: string;
  stage: DealStage;
  date: string;
  date_type: 'expected_close' | 'lease_start' | 'actual_close';
  commission_amount?: number;
}

// Stage configuration for UI
export const DEAL_STAGES: { value: DealStage; label: string; color: string }[] = [
  { value: 'intake', label: 'Intake', color: 'bg-gray-500' },
  { value: 'qualification', label: 'Qualification', color: 'bg-blue-500' },
  { value: 'due_diligence', label: 'Due Diligence', color: 'bg-indigo-500' },
  { value: 'tenant_vetting', label: 'Tenant Vetting', color: 'bg-violet-500' },
  { value: 'loi', label: 'LOI', color: 'bg-yellow-500' },
  { value: 'under_contract', label: 'Under Contract', color: 'bg-orange-500' },
  { value: 'closed', label: 'Closed', color: 'bg-green-500' },
  { value: 'passed', label: 'Passed', color: 'bg-slate-500' },
  { value: 'dead', label: 'Dead', color: 'bg-red-500' },
];

export const ACTIVITY_TYPES: { value: ActivityType; label: string; icon: string }[] = [
  { value: 'note', label: 'Note', icon: 'FileText' },
  { value: 'call', label: 'Call', icon: 'Phone' },
  { value: 'email', label: 'Email', icon: 'Mail' },
  { value: 'meeting', label: 'Meeting', icon: 'Users' },
  { value: 'tour', label: 'Tour', icon: 'MapPin' },
  { value: 'document', label: 'Document', icon: 'File' },
];

// Helper to get stage configuration
export function getStageConfig(stage: DealStage) {
  return DEAL_STAGES.find(s => s.value === stage) || DEAL_STAGES[0];
}

// Helper to format currency
export function formatCurrency(amount: number | undefined | null): string {
  if (amount === undefined || amount === null) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

// Helper to format PSF
export function formatPSF(amount: number | undefined | null): string {
  if (amount === undefined || amount === null) return '-';
  return `$${amount.toFixed(2)}/SF`;
}
