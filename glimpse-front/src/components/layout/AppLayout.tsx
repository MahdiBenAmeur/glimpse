import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/layout/AppSidebar";
import type { ReactNode } from "react";
import { useApp } from "@/contexts/AppContext";

export function AppLayout({ children }: { children: ReactNode }) {
  const { settings } = useApp();
  return (
    <SidebarProvider key={settings.compactSidebar ? "compact" : "comfortable"} defaultOpen={!settings.compactSidebar}>
      <div className="min-h-screen flex w-full">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <header className="h-12 flex items-center border-b border-border px-4 bg-card shrink-0">
            <SidebarTrigger className="mr-3" />
          </header>
          <main className="flex-1 overflow-auto">
            {children}
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
