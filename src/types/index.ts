/**
 * Claude Ventures - Core Type Definitions
 *
 * Tracks ventures (creative, research, professional initiatives) with
 * priority ranking based on external deadlines, manual priority,
 * strategic alignment, and financial signals.
 */

// =============================================================================
// Enums & Constants
// =============================================================================

export const VentureType = {
  Creative: "creative",
  Research: "research",
  Consulting: "consulting",
  Infrastructure: "infrastructure",
  Community: "community",
} as const;

export type VentureTypeValue = (typeof VentureType)[keyof typeof VentureType];

export const VentureStage = {
  Seed: "seed",
  Exploring: "exploring",
  Active: "active",
  Sustaining: "sustaining",
  Dormant: "dormant",
  Harvesting: "harvesting",
} as const;

export type VentureStageValue = (typeof VentureStage)[keyof typeof VentureStage];

export const VENTURE_STAGES_ORDERED: VentureStageValue[] = [
  "seed",
  "exploring",
  "active",
  "sustaining",
  "dormant",
  "harvesting",
];

export const PriorityLevel = {
  Critical: "critical",
  High: "high",
  Medium: "medium",
  Low: "low",
  None: "none",
} as const;

export type PriorityLevelValue = (typeof PriorityLevel)[keyof typeof PriorityLevel];

export const RateType = {
  Hourly: "hourly",
  Fixed: "fixed",
  Retainer: "retainer",
  Equity: "equity",
} as const;

export type RateTypeValue = (typeof RateType)[keyof typeof RateType];

export const DeadlineType = {
  External: "external",
  Internal: "internal",
} as const;

export type DeadlineTypeValue = (typeof DeadlineType)[keyof typeof DeadlineType];

export const FundingStatus = {
  Unfunded: "unfunded",
  Seeking: "seeking",
  Partial: "partial",
  Funded: "funded",
} as const;

export type FundingStatusValue = (typeof FundingStatus)[keyof typeof FundingStatus];

// =============================================================================
// People Types
// =============================================================================

export interface CoVenturer {
  name: string;
  role: string;
  contact?: string;
}

// =============================================================================
// Financial Types
// =============================================================================

export interface MoneyAmount {
  amount: number;
  currency: string;
}

export interface RateInfo {
  type: RateTypeValue;
  hourly_rate?: MoneyAmount;
  fixed_amount?: MoneyAmount;
  retainer_monthly?: MoneyAmount;
  equity_percentage?: number;
  estimated_hours?: number;
}

export interface Invoice {
  id: string;
  date: string;
  amount: MoneyAmount;
  description?: string;
  paid: boolean;
  paid_date?: string;
}

export interface FundingOpportunity {
  name: string;
  stage: string;
  amount?: MoneyAmount;
  deadline?: string;
}

export interface FinancialTracking {
  status: FundingStatusValue;
  rate?: RateInfo;
  opportunities?: FundingOpportunity[];
  invoices: Invoice[];
  total_invoiced: MoneyAmount;
  total_received: MoneyAmount;
  outstanding: MoneyAmount;
  next_invoice_date?: string;
  next_invoice_amount?: MoneyAmount;
}

// =============================================================================
// Deadline & Milestone Types
// =============================================================================

export interface Deadline {
  date: string;
  time?: string;
  timezone?: string;
  label?: string;
  description?: string;
  type: DeadlineTypeValue;
}

export interface Deliverable {
  id: string;
  title: string;
  description?: string;
  deadline?: Deadline;
  completed: boolean;
  completed_at?: string;
}

export interface Milestone {
  id: string;
  title: string;
  description?: string;
  status: "pending" | "in-progress" | "completed";
  deadline?: Deadline;
  deliverables: Deliverable[];
  completed: boolean;
  completed_at?: string;
}

// =============================================================================
// Data Path Types (Layer 3 references)
// =============================================================================

export interface VentureDataPaths {
  root: string;
  transcripts?: string;
  media?: string;
  datasets?: string;
}

// =============================================================================
// Integration Types
// =============================================================================

export interface VentureIntegrations {
  github?: {
    repo: string;
    issues_label?: string;
  };

  logging?: {
    tags?: string[];
  };

  matrix?: {
    channel?: string;
  };

  transcript_sessions?: string[];

  resources?: Array<{
    url: string;
    title?: string;
    type?: "doc" | "api" | "reference" | "tool" | "drive" | "other";
  }>;
}

// =============================================================================
// Venture Type
// =============================================================================

export interface Venture {
  id: string;
  title: string;
  description?: string;

  type: VentureTypeValue;
  stage: VentureStageValue;
  priority: PriorityLevelValue;

  calculated_priority?: number;

  created_at: string;
  updated_at: string;
  started_at?: string;

  deadlines: Deadline[];
  milestones: Milestone[];

  co_venturers: CoVenturer[];

  financial?: FinancialTracking;

  tags: string[];

  links?: Record<string, string>;
  related_ventures: string[];

  data?: VentureDataPaths;

  integrations?: VentureIntegrations;

  notes?: string;

  file_path?: string;
}

export type CreateVentureInput = Omit<
  Venture,
  "id" | "created_at" | "updated_at" | "calculated_priority" | "file_path"
>;

export type UpdateVentureInput = Partial<
  Omit<Venture, "id" | "created_at" | "file_path">
>;

// =============================================================================
// Query & Filter Types
// =============================================================================

export interface VentureFilter {
  type?: VentureTypeValue | VentureTypeValue[];
  stage?: VentureStageValue | VentureStageValue[];
  priority?: PriorityLevelValue | PriorityLevelValue[];
  tags?: string[];
  has_deadline?: boolean;
  overdue?: boolean;
  due_within_days?: number;
  min_priority?: number;
}

export type SortField =
  | "priority"
  | "deadline"
  | "created"
  | "updated"
  | "stage"
  | "title";
export type SortOrder = "asc" | "desc";

export interface VentureQuery {
  filter?: VentureFilter;
  sort_by?: SortField;
  sort_order?: SortOrder;
  limit?: number;
  offset?: number;
}

// =============================================================================
// Priority Calculation Types
// =============================================================================

export interface PriorityWeights {
  deadline_urgency: number;
  manual_priority: number;
  strategic_alignment: number;
  financial_signal: number;
  stage_modifier: number;
}

export const DEFAULT_PRIORITY_WEIGHTS: PriorityWeights = {
  deadline_urgency: 0.45,
  manual_priority: 0.30,
  strategic_alignment: 0.15,
  financial_signal: 0.05,
  stage_modifier: 0.05,
};

export interface PriorityContext {
  now: Date;
  weights: PriorityWeights;
  all_ventures?: Venture[];
}

export interface PriorityBreakdown {
  deadline_urgency: number;
  manual_priority: number;
  strategic_alignment: number;
  financial_signal: number;
  stage_modifier: number;
  total_raw: number;
}

export interface PriorityScore {
  total: number;
  breakdown: PriorityBreakdown;
  nearest_deadline?: string;
  days_until_deadline?: number;
}

// =============================================================================
// Store Interface
// =============================================================================

export interface VentureStore {
  create(input: CreateVentureInput): Promise<Venture>;
  get(id: string): Promise<Venture | null>;
  update(id: string, input: UpdateVentureInput): Promise<Venture>;
  delete(id: string): Promise<void>;

  list(query?: VentureQuery): Promise<Venture[]>;
  search(text: string): Promise<Venture[]>;

  addMilestone(
    ventureId: string,
    milestone: Omit<Milestone, "id">
  ): Promise<Milestone>;
  updateMilestone(
    ventureId: string,
    milestoneId: string,
    updates: Partial<Milestone>
  ): Promise<Milestone>;
  completeMilestone(ventureId: string, milestoneId: string): Promise<void>;

  addDeliverable(
    ventureId: string,
    milestoneId: string,
    deliverable: Omit<Deliverable, "id">
  ): Promise<Deliverable>;
  completeDeliverable(
    ventureId: string,
    milestoneId: string,
    deliverableId: string
  ): Promise<void>;

  transitionStage(
    ventureId: string,
    newStage: VentureStageValue,
    notes?: string
  ): Promise<Venture>;

  addInvoice(ventureId: string, invoice: Omit<Invoice, "id">): Promise<Invoice>;
  markInvoicePaid(ventureId: string, invoiceId: string): Promise<void>;
}

// =============================================================================
// Config Types
// =============================================================================

export interface VenturesConfig {
  priority_weights: PriorityWeights;
  default_currency: string;
  data_drive_path: string;
}

export const DEFAULT_CONFIG: VenturesConfig = {
  priority_weights: DEFAULT_PRIORITY_WEIGHTS,
  default_currency: "CAD",
  data_drive_path: "/mnt/data-24tb/10-19_Projects",
};
