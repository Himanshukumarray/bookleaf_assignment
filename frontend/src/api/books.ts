import { api } from "./client";
import type { AuthorDashboard, Book } from "../types";

export const fetchBooks = async (): Promise<Book[]> => (await api.get<Book[]>("/books")).data;

export const fetchAuthorDashboard = async (): Promise<AuthorDashboard> =>
  (await api.get<AuthorDashboard>("/author/dashboard")).data;
