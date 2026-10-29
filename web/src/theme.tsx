import { createContext, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from "react";

export type Theme = "dark" | "light";

type ThemeContextValue = {
  theme: Theme;
  toggleTheme: () => void;
};

const THEME_STORAGE_KEY = "pe3-theme";
const ThemeContext = createContext<ThemeContextValue | null>(null);

function initialTheme(): Theme {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  return saved === "light" || saved === "dark" ? saved : "dark";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const value = useMemo(
    () => ({ theme, toggleTheme: () => setTheme((current) => (current === "dark" ? "light" : "dark")) }),
    [theme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used inside ThemeProvider");
  return value;
}

export function chartTheme(theme: Theme) {
  return theme === "light"
    ? {
        text: "#172033",
        grid: "rgba(23, 32, 51, 0.12)",
        guide: "rgba(23, 32, 51, 0.38)",
        average: "rgba(23, 32, 51, 0.72)",
        remainder: "rgba(23, 32, 51, 0.10)",
      }
    : {
        text: "#e8eefc",
        grid: "rgba(255, 255, 255, 0.08)",
        guide: "rgba(255, 255, 255, 0.35)",
        average: "rgba(255, 255, 255, 0.75)",
        remainder: "rgba(255, 255, 255, 0.08)",
      };
}
