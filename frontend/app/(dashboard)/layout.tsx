"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/organisms/Sidebar";
import { Header } from "@/components/organisms/Header";
import { useAuthStore } from "@/store/auth.store";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    // Check localStorage as fallback (for legacy apiClient compatibility)
    const token = localStorage.getItem("access_token");
    if (!isAuthenticated && !token) {
      router.replace("/login");
    }
  }, [isAuthenticated, router]);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
