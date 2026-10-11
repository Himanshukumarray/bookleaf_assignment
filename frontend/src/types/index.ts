export type Role = "AUTHOR" | "ADMIN";
export type TicketStatus = "OPEN" | "IN_PROGRESS" | "RESOLVED" | "CLOSED";
export type Priority = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type DecisionSource = "AI" | "RULE" | "MANUAL" | "DEFAULT";
export type AIStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";

export const CATEGORIES = [
  "Royalty & Payments",
  "ISBN & Metadata Issues",
  "Printing & Quality",
  "Distribution & Availability",
  "Book Status & Production Updates",
  "General Inquiry",
] as const;
export type Category = (typeof CATEGORIES)[number];

export const STATUSES: TicketStatus[] = ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"];
export const PRIORITIES: Priority[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

export interface Author {
  author_id: string;
  name: string;
  email: string;
  phone: string | null;
  city: string | null;
  joined_date: string | null;
}

export interface User {
  id: number;
  email: string;
  role: Role;
  author: Author | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Book {
  book_id: string;
  title: string;
  isbn: string | null;
  genre: string | null;
  publication_date: string | null;
  status: string;
  mrp: number | null;
  author_royalty_per_copy: number | null;
  total_copies_sold: number;
  total_royalty_earned: number;
  royalty_paid: number;
  royalty_pending: number;
  last_royalty_payout_date: string | null;
  print_partner: string | null;
  available_on: string[];
}

export interface BookRef {
  book_id: string;
  title: string;
  status: string;
}

export interface Ticket {
  ticket_id: string;
  book: BookRef | null;
  subject: string;
  description: string;
  category: Category | null;
  priority: Priority;
  status: TicketStatus;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface TicketCreate {
  book_id: string | null;
  subject: string;
  description: string;
}

export interface Message {
  id: number;
  sender_role: "AUTHOR" | "ADMIN";
  sender_label: string;
  message: string;
  created_at: string;
}

export interface AdminMessage extends Message {
  is_ai_assisted: boolean;
}

export interface BookStatusCount {
  status: string;
  count: number;
}

export interface AuthorDashboard {
  total_books: number;
  open_tickets: number;
  total_royalty_earned: number;
  total_royalty_paid: number;
  total_royalty_pending: number;
  recent_tickets: Ticket[];
  book_status_overview: BookStatusCount[];
}

export interface AdminTicketSummary {
  ticket_id: string;
  author: { author_id: string; name: string };
  book: BookRef | null;
  subject: string;
  category: Category | null;
  category_source: DecisionSource;
  category_confidence: number | null;
  priority: Priority;
  priority_source: DecisionSource;
  priority_confidence: number | null;
  status: TicketStatus;
  ai_status: AIStatus;
  needs_human_attention: boolean;
  assigned_admin_email: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminTicketPage {
  items: AdminTicketSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface QueueFilters {
  status?: TicketStatus | "";
  category?: Category | "";
  priority?: Priority | "";
  assignment?: "unassigned" | "assigned" | "me" | "";
  author?: string;
  book?: string;
  date_from?: string;
  date_to?: string;
  q?: string;
  sort?: "urgency" | "newest" | "oldest" | "updated";
  page?: number;
  page_size?: number;
}

export interface KnowledgeRef {
  section: string;
  title: string;
}

export interface AIDraft {
  id: number;
  draft: string;
  model: string;
  prompt_version: string;
  grounding_warnings: string[];
  knowledge: KnowledgeRef[];
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number;
  created_at: string;
}

export interface AIRun {
  id: number;
  operation: string;
  model: string;
  prompt_version: string;
  status: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  attempts: number;
  error_type: string | null;
  created_at: string;
}

export interface InternalNote {
  id: number;
  admin_email: string;
  note: string;
  created_at: string;
}

export interface TicketEvent {
  event_type: string;
  old_value: string | null;
  new_value: string | null;
  created_at: string;
}

export interface AdminTicketDetail {
  ticket: AdminTicketSummary;
  description: string;
  ai_reasoning: string | null;
  author: Author;
  book: Book | null;
  messages: AdminMessage[];
  internal_notes: InternalNote[];
  ai_draft: AIDraft | null;
  knowledge_used: KnowledgeRef[];
  ai_runs: AIRun[];
  events: TicketEvent[];
}

export interface AdminDashboard {
  open_tickets: number;
  unresolved_tickets: number;
  critical_tickets: number;
  high_priority_tickets: number;
  unassigned_tickets: number;
  ai_failed_tickets: number;
  by_category: { category: Category | null; count: number }[];
  recent_activity: {
    ticket_id: string;
    event_type: string;
    old_value: string | null;
    new_value: string | null;
    created_at: string;
  }[];
}

export interface TicketUpdate {
  category?: Category;
  priority?: Priority;
  status?: TicketStatus;
}

export interface SocketEvent {
  type: string;
  ticket_id: string;
  timestamp: string;
}
