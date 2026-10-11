import { api } from "./client";
import type {
  AdminDashboard,
  AdminMessage,
  AdminTicketDetail,
  AdminTicketPage,
  AdminTicketSummary,
  AIDraft,
  InternalNote,
  QueueFilters,
  TicketUpdate,
} from "../types";

const clean = (filters: QueueFilters) =>
  Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== "" && v !== undefined && v !== null));

export const fetchAdminDashboard = async (): Promise<AdminDashboard> =>
  (await api.get<AdminDashboard>("/admin/dashboard")).data;

export const fetchQueue = async (filters: QueueFilters): Promise<AdminTicketPage> =>
  (await api.get<AdminTicketPage>("/admin/tickets", { params: clean(filters) })).data;

export const fetchAdminTicket = async (id: string): Promise<AdminTicketDetail> =>
  (await api.get<AdminTicketDetail>(`/admin/tickets/${id}`)).data;

export const updateTicket = async (id: string, payload: TicketUpdate): Promise<AdminTicketSummary> =>
  (await api.patch<AdminTicketSummary>(`/admin/tickets/${id}`, payload)).data;

export const assignToMe = async (id: string): Promise<AdminTicketSummary> =>
  (await api.post<AdminTicketSummary>(`/admin/tickets/${id}/assign`, {})).data;

export const addNote = async (id: string, note: string): Promise<InternalNote> =>
  (await api.post<InternalNote>(`/admin/tickets/${id}/notes`, { note })).data;

export const sendResponse = async (id: string, message: string, aiDraftId: number | null): Promise<AdminMessage> =>
  (await api.post<AdminMessage>(`/admin/tickets/${id}/messages`, { message, ai_draft_id: aiDraftId })).data;

export const regenerateDraft = async (id: string): Promise<AIDraft> =>
  (await api.post<AIDraft>(`/admin/tickets/${id}/ai-draft`)).data;

export const retryAnalysis = async (id: string): Promise<AdminTicketSummary> =>
  (await api.post<AdminTicketSummary>(`/admin/tickets/${id}/ai-retry`)).data;
