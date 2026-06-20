import { createContext, useEffect, useState, type ReactNode } from "react";

type Theme = "system" | "light" | "dark";

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

export const ThemeContext = createContext<ThemeContextType | null>(null);

/**
 * Checks if the system preference is dark mode.
 */
function getSystemDark() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/**
 * Provides theme state and management to the application.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    return (localStorage.getItem("glimpse-theme") as Theme) || "system";
  });

  const setTheme = (t: Theme) => {
    setThemeState(t);
    localStorage.setItem("glimpse-theme", t);
  };

  useEffect(() => {
    const root = document.documentElement;
    const applyTheme = () => {
      const isDark = theme === "dark" || (theme === "system" && getSystemDark());
      root.classList.toggle("dark", isDark);
    };
    applyTheme();

    if (theme === "system") {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const handler = () => applyTheme();
      mq.addEventListener("change", handler);
      return () => mq.removeEventListener("change", handler);
    }
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}


