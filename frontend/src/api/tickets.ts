import { api } from "./client";
import type { Message, Ticket, TicketCreate } from "../types";

export const fetchTickets = async (): Promise<Ticket[]> => (await api.get<Ticket[]>("/tickets")).data;

export const fetchTicket = async (id: string): Promise<Ticket> => (await api.get<Ticket>(`/tickets/${id}`)).data;

export const createTicket = async (payload: TicketCreate): Promise<Ticket> =>
  (await api.post<Ticket>("/tickets", payload)).data;

export const fetchMessages = async (id: string): Promise<Message[]> =>
  (await api.get<Message[]>(`/tickets/${id}/messages`)).data;

export const postMessage = async (id: string, message: string): Promise<Message> =>
  (await api.post<Message>(`/tickets/${id}/messages`, { message })).data;
