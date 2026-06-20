import { Loader2 } from "lucide-react";
import { useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes, Navigate, useLocation } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppProvider } from "@/contexts/AppContext";
import { useApp } from "@/contexts/useApp";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { AppLayout } from "@/components/layout/AppLayout";
import OnboardingPage from "@/pages/onboarding/OnboardingPage";
import SearchPage from "@/pages/SearchPage";
import PeoplePage from "@/pages/PeoplePage";
import PersonDetailPage from "@/pages/PersonDetailPage";
import FavoritesPage from "@/pages/FavoritesPage";
import CollectionsPage from "@/pages/CollectionsPage";
import CollectionDetailPage from "@/pages/CollectionDetailPage";
import SavedSearchesPage from "@/pages/SavedSearchesPage";
import IndexPage from "@/pages/IndexPage";
import SettingsPage from "@/pages/SettingsPage";
import NotFound from "@/pages/NotFound";

const queryClient = new QueryClient();
const LAST_ROUTE_KEY = "glimpse-last-route";

function getSavedRoute() {
  const saved = localStorage.getItem(LAST_ROUTE_KEY);
  if (!saved || !saved.startsWith("/")) {
    return "/search";
  }
  return saved === "/" ? "/search" : saved;
}

function AppRoutes() {
  const { isFirstLaunch, isHydrating, isWorking, busyMessage, showWorkingOverlay, settings } = useApp();
  const location = useLocation();

  useEffect(() => {
    if (isFirstLaunch || !settings.rememberLastPage) {
      return;
    }
    localStorage.setItem(LAST_ROUTE_KEY, location.pathname);
  }, [isFirstLaunch, location.pathname, settings.rememberLastPage]);

  if (isHydrating) {
    return <BootSplash />;
  }

  if (isFirstLaunch) {
    return <><OnboardingPage />{isWorking && showWorkingOverlay && <WorkingOverlay message={busyMessage} />}</>;
  }

  return (
    <>
      <AppLayout>
        <Routes>
          <Route path="/" element={<Navigate to={settings.rememberLastPage ? getSavedRoute() : "/search"} replace />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/people" element={<PeoplePage />} />
          <Route path="/people/:id" element={<PersonDetailPage />} />
          <Route path="/favorites" element={<FavoritesPage />} />
          <Route path="/collections" element={<CollectionsPage />} />
          <Route path="/collections/:id" element={<CollectionDetailPage />} />
          <Route path="/saved-searches" element={<SavedSearchesPage />} />
          <Route path="/index-manager" element={<IndexPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AppLayout>
      {isWorking && showWorkingOverlay && <WorkingOverlay message={busyMessage} />}
    </>
  );
}

function BootSplash() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
      <div className="flex items-center gap-3 rounded-2xl border border-border bg-card px-5 py-4 shadow-sm">
        <Loader2 className="w-5 h-5 animate-spin text-primary" />
        <div>
          <p className="text-sm font-medium">Loading your library</p>
          <p className="text-xs text-muted-foreground">Syncing models, folders, and index state.</p>
        </div>
      </div>
    </div>
  );
}

function WorkingOverlay({ message }: { message: string | null }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 backdrop-blur-sm">
      <div className="flex items-center gap-3 rounded-2xl border border-border bg-card px-5 py-4 shadow-lg">
        <Loader2 className="w-5 h-5 animate-spin text-primary" />
        <div>
          <p className="text-sm font-medium text-foreground">{message ?? "Working..."}</p>
          <p className="text-xs text-muted-foreground">Please keep this window open.</p>
        </div>
      </div>
    </div>
  );
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <AppProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </AppProvider>
      </TooltipProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
