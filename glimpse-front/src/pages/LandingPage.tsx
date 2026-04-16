import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Sparkles, Search, Fingerprint, Lock, ChevronRight, Image as ImageIcon } from "lucide-react";

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans selection:bg-primary/30">
      {/* Navigation Bar */}
      <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/60 backdrop-blur-md">
        <div className="container mx-auto flex h-16 items-center flex-row justify-between px-6">
          <div className="flex items-center gap-2">
            <div className="bg-primary/10 p-1.5 rounded-lg border border-primary/20">
              <Sparkles className="w-5 h-5 text-primary" />
            </div>
            <span className="font-bold text-xl tracking-tight">Glimpse</span>
          </div>
          <div className="flex items-center gap-4">
            <Button variant="ghost" className="text-sm hidden sm:inline-flex" onClick={() => navigate("/search")}>
              Log in
            </Button>
            <Button className="text-sm font-medium shadow-lg shadow-primary/20" onClick={() => navigate("/search")}>
              Launch App
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1 flex flex-col items-center justify-center text-center px-4 relative overflow-hidden">
        {/* Background Gradients */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/20 rounded-full blur-[120px] pointer-events-none opacity-50 dark:opacity-20" />
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-blue-500/20 rounded-full blur-[100px] pointer-events-none opacity-40 dark:opacity-10" />

        <div className="max-w-4xl pt-24 pb-16 relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-muted border border-border/50 text-sm font-medium text-muted-foreground mb-8 cursor-default hover:bg-muted/80 transition-colors">
            <Sparkles className="w-4 h-4 text-primary" />
            <span>Introducing Glimpse AI Model 1.0</span>
          </div>
          
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-6 leading-tight">
            Your Visual Memory, <br className="hidden md:block" />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-blue-500 to-purple-500">
              Powered by AI.
            </span>
          </h1>
          
          <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed">
            Search your entire photo collection using natural language, identify faces instantly, and organize your memories without sacrificing your privacy. All processed locally on your machine.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button size="lg" className="h-12 px-8 text-base font-semibold rounded-full shadow-xl shadow-primary/25 hover:scale-105 transition-transform" onClick={() => navigate("/search")}>
              Get Started
              <ChevronRight className="w-5 h-5 ml-1.5" />
            </Button>
            <Button size="lg" variant="outline" className="h-12 px-8 text-base font-semibold rounded-full bg-background/50 backdrop-blur-sm border-border hover:bg-muted transition-colors" onClick={() => navigate("/search")}>
              View Demo
            </Button>
          </div>
        </div>

        {/* Features Grid */}
        <div className="max-w-6xl w-full grid grid-cols-1 md:grid-cols-3 gap-6 px-6 py-24 z-10">
          <FeatureCard 
            icon={<Search className="w-6 h-6 text-blue-500" />}
            title="Semantic Search"
            description="Find photos by describing them naturally. 'A red car at sunset' or 'dog playing in the snow'."
            delay="0"
          />
          <FeatureCard 
            icon={<Fingerprint className="w-6 h-6 text-purple-500" />}
            title="Face Recognition"
            description="Automatically clusters and identifies people across your entire dataset with high precision."
            delay="100"
          />
          <FeatureCard 
            icon={<Lock className="w-6 h-6 text-emerald-500" />}
            title="Privacy First"
            description="Your photos never leave your device. All machine learning inference happens entirely locally."
            delay="200"
          />
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full border-t border-border/40 py-8 bg-muted/20">
        <div className="container mx-auto px-6 flex flex-col md:flex-row items-center justify-between text-sm text-muted-foreground">
          <div className="flex items-center gap-2 mb-4 md:mb-0">
            <ImageIcon className="w-4 h-4" />
            <span>© 2026 Glimpse. All rights reserved.</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#" className="hover:text-foreground transition-colors">Privacy Policy</a>
            <a href="#" className="hover:text-foreground transition-colors">Terms of Service</a>
            <a href="#" className="hover:text-foreground transition-colors">GitHub</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, description, delay }: { icon: React.ReactNode; title: string; description: string; delay: string }) {
  return (
    <div 
      className={`group flex flex-col p-8 rounded-2xl bg-card border border-border/50 shadow-sm hover:shadow-xl hover:-translate-y-1 hover:border-primary/30 transition-all duration-300`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-primary/10 transition-all duration-300">
        {icon}
      </div>
      <h3 className="text-xl font-semibold mb-3">{title}</h3>
      <p className="text-muted-foreground leading-relaxed">
        {description}
      </p>
    </div>
  );
}
