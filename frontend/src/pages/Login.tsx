import { zodResolver } from "@hookform/resolvers/zod";
import { BookOpen } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router-dom";
import { z } from "zod";

import { getErrorMessage } from "../api/client";
import { Button, FieldError } from "../components/common/ui";
import { homePathFor } from "../components/layout/AppShell";
import { useAuth } from "../hooks/useAuth";

const schema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});
type FormValues = z.infer<typeof schema>;

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string>();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormValues>({ resolver: zodResolver(schema) });

  if (user) return <Navigate to={homePathFor(user.role)} replace />;

  const onSubmit = handleSubmit(async (values) => {
    setServerError(undefined);
    try {
      const signedIn = await login(values.email, values.password);
      navigate(homePathFor(signedIn.role), { replace: true });
    } catch (e) {
      setServerError(getErrorMessage(e, "Sign in failed."));
    }
  });

  return (
    <div className="grid min-h-screen place-items-center bg-gradient-to-br from-brand-50 via-white to-slate-100 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center">
          <span className="grid h-12 w-12 place-items-center rounded-xl bg-brand-600 text-white"><BookOpen className="h-6 w-6" /></span>
          <h1 className="mt-3 text-xl font-bold">BookLeaf Support Portal</h1>
          <p className="text-sm text-slate-500">Sign in to continue</p>
        </div>
        <form onSubmit={onSubmit} noValidate className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div>
            <label htmlFor="email" className="label">Email</label>
            <input id="email" type="email" autoComplete="username" className="input" {...register("email")} aria-invalid={!!errors.email} />
            <FieldError message={errors.email?.message} />
          </div>
          <div>
            <label htmlFor="password" className="label">Password</label>
            <input id="password" type="password" autoComplete="current-password" className="input" {...register("password")} aria-invalid={!!errors.password} />
            <FieldError message={errors.password?.message} />
          </div>
          {serverError && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{serverError}</p>}
          <Button type="submit" className="w-full" loading={isSubmitting}>Sign in</Button>
        </form>
        <p className="mt-4 text-center text-xs text-slate-500">
          Demo accounts are listed in the project README (development credentials only).
        </p>
      </div>
    </div>
  );
}
