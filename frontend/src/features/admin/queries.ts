import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addNote,
  assignToMe,
  fetchAdminDashboard,
  fetchAdminTicket,
  fetchQueue,
  regenerateDraft,
  retryAnalysis,
  sendResponse,
  updateTicket,
} from "../../api/admin";
import type { QueueFilters, TicketUpdate } from "../../types";

export const useAdminDashboard = () => useQuery({ queryKey: ["admin-dashboard"], queryFn: fetchAdminDashboard });

export const useQueue = (filters: QueueFilters) =>
  useQuery({ queryKey: ["admin-tickets", filters], queryFn: () => fetchQueue(filters), placeholderData: keepPreviousData });

export const useAdminTicket = (id: string) =>
  useQuery({ queryKey: ["admin-ticket", id], queryFn: () => fetchAdminTicket(id), refetchInterval: 30_000 });

/** Every admin mutation refreshes the open ticket and any list that shows it. */
function useTicketMutation<TVars, TResult>(id: string, fn: (vars: TVars) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-ticket", id] });
      void queryClient.invalidateQueries({ queryKey: ["admin-tickets"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
    },
  });
}

export const useUpdateTicket = (id: string) => useTicketMutation(id, (payload: TicketUpdate) => updateTicket(id, payload));
export const useAssignToMe = (id: string) => useTicketMutation(id, () => assignToMe(id));
export const useAddNote = (id: string) => useTicketMutation(id, (note: string) => addNote(id, note));
export const useSendResponse = (id: string) =>
  useTicketMutation(id, (vars: { message: string; aiDraftId: number | null }) => sendResponse(id, vars.message, vars.aiDraftId));
export const useRegenerateDraft = (id: string) => useTicketMutation(id, () => regenerateDraft(id));
export const useRetryAnalysis = (id: string) => useTicketMutation(id, () => retryAnalysis(id));
