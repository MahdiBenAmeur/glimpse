import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppProvider, useApp } from "@/contexts/AppContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { CollectionProvider } from "@/contexts/CollectionContext";
import { AppLayout } from "@/components/layout/AppLayout";
import LandingPage from "@/pages/LandingPage";
import ModelSetupPage from "@/pages/onboarding/ModelSetupPage";
import FolderSelectionPage from "@/pages/onboarding/FolderSelectionPage";
import InitialIndexingPage from "@/pages/onboarding/InitialIndexingPage";
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

function AppRoutes() {
  const { isFirstLaunch, onboardingStep } = useApp();

  if (isFirstLaunch) {
    if (onboardingStep === 0) return <ModelSetupPage />;
    if (onboardingStep === 1) return <FolderSelectionPage />;
    if (onboardingStep === 2) return <InitialIndexingPage />;
  }

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route element={<AppLayout />}>
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
      </Route>
    </Routes>
  );
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <AppProvider>
          <CollectionProvider>
            <BrowserRouter
              future={{ v7_relativeSplatPath: true }}
            >
              <AppRoutes />
            </BrowserRouter>
          </CollectionProvider>
        </AppProvider>
      </TooltipProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
