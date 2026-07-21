import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  moneyApi,
  type CategoryDeletePreview,
  type CategoryInfo,
  type CategoryMergeResult,
} from "./api";

type CategoriesContextValue = {
  categories: CategoryInfo[];
  slugs: string[];
  loading: boolean;
  refresh: () => Promise<void>;
  createCategory: (name: string) => Promise<CategoryInfo>;
  renameCategory: (slug: string, name: string) => Promise<CategoryInfo>;
  deleteCategory: (slug: string) => Promise<{
    transactions_recategorized: number;
    transactions_unclear: number;
  }>;
  deleteCategoryPreview: (slug: string) => Promise<CategoryDeletePreview>;
  mergeCategory: (slug: string, targetSlug: string) => Promise<CategoryMergeResult>;
};

const CategoriesContext = createContext<CategoriesContextValue | null>(null);

const BUDGET_EXCLUDE = new Set(["Income", "Transfers", "Unclear"]);

export function budgetCategorySlugs(categories: CategoryInfo[]): string[] {
  return categories.filter((c) => !BUDGET_EXCLUDE.has(c.slug)).map((c) => c.slug);
}

export function CategoriesProvider({ children }: { children: ReactNode }) {
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const res = await moneyApi.categories();
    setCategories(res.categories);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh().catch(() => setLoading(false));
  }, [refresh]);

  const slugs = useMemo(() => categories.map((c) => c.slug), [categories]);

  const createCategory = useCallback(
    async (name: string) => {
      const created = await moneyApi.createCategory(name);
      await refresh();
      return created;
    },
    [refresh],
  );

  const renameCategory = useCallback(
    async (slug: string, name: string) => {
      const updated = await moneyApi.renameCategory(slug, name);
      await refresh();
      return updated;
    },
    [refresh],
  );

  const deleteCategory = useCallback(
    async (slug: string) => {
      const result = await moneyApi.deleteCategory(slug);
      await refresh();
      return result;
    },
    [refresh],
  );

  const deleteCategoryPreview = useCallback(
    (slug: string) => moneyApi.deleteCategoryPreview(slug),
    [],
  );

  const mergeCategory = useCallback(
    async (slug: string, targetSlug: string) => {
      const result = await moneyApi.mergeCategory(slug, targetSlug);
      await refresh();
      return result;
    },
    [refresh],
  );

  const value = useMemo(
    () => ({
      categories,
      slugs,
      loading,
      refresh,
      createCategory,
      renameCategory,
      deleteCategory,
      deleteCategoryPreview,
      mergeCategory,
    }),
    [
      categories,
      slugs,
      loading,
      refresh,
      createCategory,
      renameCategory,
      deleteCategory,
      deleteCategoryPreview,
      mergeCategory,
    ],
  );

  return <CategoriesContext.Provider value={value}>{children}</CategoriesContext.Provider>;
}

export function useCategories() {
  const ctx = useContext(CategoriesContext);
  if (!ctx) throw new Error("useCategories must be used within CategoriesProvider");
  return ctx;
}
