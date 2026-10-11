import { Navigate, Route, Routes } from "react-router-dom";

import { PageSkeleton } from "./components/common/ui";
import { ProtectedLayout, homePathFor } from "./components/layout/AppShell";
import { useAuth } from "./hooks/useAuth";
import AdminDashboard from "./pages/admin/Dashboard";
import AdminTicketDetail from "./pages/admin/TicketDetail";
import TicketQueue from "./pages/admin/TicketQueue";
import AuthorDashboard from "./pages/author/Dashboard";
import Books from "./pages/author/Books";
import NewTicket from "./pages/author/NewTicket";
import AuthorTicketDetail from "./pages/author/TicketDetail";
import Tickets from "./pages/author/Tickets";
import Login from "./pages/Login";

function RootRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-10"><PageSkeleton /></div>;
  return <Navigate to={user ? homePathFor(user.role) : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/author" element={<ProtectedLayout role="AUTHOR" />}>
        <Route index element={<AuthorDashboard />} />
        <Route path="books" element={<Books />} />
        <Route path="tickets" element={<Tickets />} />
        <Route path="tickets/new" element={<NewTicket />} />
        <Route path="tickets/:ticketId" element={<AuthorTicketDetail />} />
      </Route>
      <Route path="/admin" element={<ProtectedLayout role="ADMIN" />}>
        <Route index element={<AdminDashboard />} />
        <Route path="tickets" element={<TicketQueue />} />
        <Route path="tickets/:ticketId" element={<AdminTicketDetail />} />
      </Route>
      <Route path="/" element={<RootRedirect />} />
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  );
}
