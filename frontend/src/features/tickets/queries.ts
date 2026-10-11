import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createTicket, fetchMessages, fetchTicket, fetchTickets, postMessage } from "../../api/tickets";

export const useTickets = () => useQuery({ queryKey: ["tickets"], queryFn: fetchTickets });

export const useTicket = (id: string) => useQuery({ queryKey: ["ticket", id], queryFn: () => fetchTicket(id) });

/** Also refetches every 30s as a safety net if the WebSocket is down. */
export const useMessages = (id: string) =>
  useQuery({ queryKey: ["messages", id], queryFn: () => fetchMessages(id), refetchInterval: 30_000 });

export function useCreateTicket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createTicket,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
      void queryClient.invalidateQueries({ queryKey: ["author-dashboard"] });
    },
  });
}

export function usePostMessage(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => postMessage(id, message),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["messages", id] });
      void queryClient.invalidateQueries({ queryKey: ["ticket", id] });
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
    },
  });
}
