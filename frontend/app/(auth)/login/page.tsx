"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Briefcase, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import { Input } from "@/components/atoms/Input";
import { FormField } from "@/components/molecules/FormField";
import { apiClient } from "@/lib/apiClient";
import { useAuthStore } from "@/store/auth.store";

interface LoginResponse {
  success: boolean;
  data: {
    access_token: string;
    refresh_token: string;
    user?: {
      id: string;
      email: string;
      full_name: string;
    };
  };
}

export default function LoginPage() {
  const router = useRouter();
  const { setTokens } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const { data } = await apiClient.post<LoginResponse>("/auth/login", {
        email,
        password,
      });
      const { access_token, refresh_token } = data.data;
      setTokens(access_token, refresh_token);
      // Also set the keys that apiClient.ts interceptors use
      localStorage.setItem("access_token", access_token);
      localStorage.setItem("refresh_token", refresh_token);
      router.push("/cases");
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { message?: string } } };
      setError(
        axiosError.response?.data?.message ??
          "Credenciales incorrectas. Verifica tu email y contraseña."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="h-12 w-12 rounded-xl bg-primary flex items-center justify-center mb-4 shadow-md">
            <Briefcase className="h-6 w-6 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">CaseManager</h1>
          <p className="text-sm text-muted-foreground mt-1">Inicia sesión para continuar</p>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <FormField label="Email" htmlFor="email">
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="tu@empresa.com"
                autoComplete="email"
                required
              />
            </FormField>

            <FormField label="Contraseña" htmlFor="password">
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </FormField>

            {error && (
              <p className="text-sm text-destructive rounded-md bg-destructive/10 px-3 py-2">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full mt-1" loading={loading}>
              Iniciar sesión
            </Button>
          </form>
        </div>

        <p className="text-center text-xs text-muted-foreground mt-6">
          Case Management System © 2026
        </p>
      </div>
    </div>
  );
}
