import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { environmentStorageKey } from "../api/client";

function storageKey() {
  return environmentStorageKey("material_id");
}

export function comparisonStorageKey() {
  return environmentStorageKey("material_comparison");
}

export function clearMaterialSelections() {
  sessionStorage.removeItem(storageKey());
  sessionStorage.removeItem(comparisonStorageKey());
}

export function useMaterialSelection(restoreComparison = false) {
  const [searchParams, setSearchParams] = useSearchParams();
  const materialId = searchParams.get("material_id");
  const key = storageKey();

  useEffect(() => {
    if (materialId !== null) {
      if (materialId) sessionStorage.setItem(key, materialId);
      else sessionStorage.removeItem(key);
      return;
    }

    const comparison = restoreComparison && !searchParams.size && sessionStorage.getItem(comparisonStorageKey());
    if (comparison) {
      setSearchParams(comparison, { replace: true });
      return;
    }

    const savedMaterialId = sessionStorage.getItem(key);
    if (savedMaterialId) {
      const next = new URLSearchParams(searchParams);
      next.set("material_id", savedMaterialId);
      setSearchParams(next, { replace: true });
    }
  }, [key, materialId, restoreComparison, searchParams, setSearchParams]);

  return { materialId: materialId ?? "", searchParams, setSearchParams };
}
