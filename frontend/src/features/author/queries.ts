import { useQuery } from "@tanstack/react-query";

import { fetchAuthorDashboard, fetchBooks } from "../../api/books";

export const useBooks = () => useQuery({ queryKey: ["books"], queryFn: fetchBooks });

export const useAuthorDashboard = () => useQuery({ queryKey: ["author-dashboard"], queryFn: fetchAuthorDashboard });
