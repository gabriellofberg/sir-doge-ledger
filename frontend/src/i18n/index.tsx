import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { settingsApi } from "../api";
import { useCategories } from "../categories";
import { translations, tr, type Lang } from "./translations";

export { tr };

type I18nContextValue = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (typeof translations)[Lang];
  cat: (slug: string) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

function I18nProviderInner({ children }: { children: ReactNode }) {
  const { categories } = useCategories();
  const [lang, setLangState] = useState<Lang>(() => {
    const stored = localStorage.getItem("sir-doge-lang");
    return stored === "en" ? "en" : "sv";
  });

  useEffect(() => {
    document.documentElement.lang = lang;
    localStorage.setItem("sir-doge-lang", lang);
  }, [lang]);

  useEffect(() => {
    settingsApi
      .get()
      .then((s) => {
        if (s.language === "en" || s.language === "sv") setLangState(s.language);
        if (s.theme === "dark") document.documentElement.dataset.theme = "dark";
        else delete document.documentElement.dataset.theme;
      })
      .catch(() => undefined);
  }, []);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    settingsApi.patch({ language: next }).catch(() => undefined);
  }, []);

  const t = translations[lang];

  const nameBySlug = useMemo(
    () => new Map(categories.map((c) => [c.slug, c.name])),
    [categories],
  );

  const cat = useCallback(
    (slug: string) => {
      const translated = t.categories[slug as keyof typeof t.categories];
      if (translated) return translated;
      return nameBySlug.get(slug) ?? slug;
    },
    [t, nameBySlug],
  );

  const value = useMemo(() => ({ lang, setLang, t, cat }), [lang, setLang, t, cat]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  return <I18nProviderInner>{children}</I18nProviderInner>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
