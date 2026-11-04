import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { environmentStorageKey } from "../api/client";

function storageKey() {
  return environmentStorageKey("material_id");
}

export function clearMaterialSelections() {
  sessionStorage.removeItem(storageKey());
}

export function useMaterialSelection() {
  const [searchParams, setSearchParams] = useSearchParams();
  const materialId = searchParams.get("material_id");
  const key = storageKey();

  useEffect(() => {
    if (materialId !== null) {
      if (materialId) sessionStorage.setItem(key, materialId);
      else sessionStorage.removeItem(key);
      return;
    }

    const savedMaterialId = sessionStorage.getItem(key);
    if (savedMaterialId) {
      const next = new URLSearchParams(searchParams);
      next.set("material_id", savedMaterialId);
      setSearchParams(next, { replace: true });
    }
  }, [key, materialId, searchParams, setSearchParams]);

  return { materialId: materialId ?? "", searchParams, setSearchParams };
}
