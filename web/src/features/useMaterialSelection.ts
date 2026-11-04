import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { environmentStorageKey } from "../api/client";

type MaterialPage = "charts" | "ratings";

function storageKey(page: MaterialPage) {
  return environmentStorageKey(`${page}.material_id`);
}

export function clearMaterialSelections() {
  sessionStorage.removeItem(storageKey("charts"));
  sessionStorage.removeItem(storageKey("ratings"));
}

export function useMaterialSelection(page: MaterialPage) {
  const [searchParams, setSearchParams] = useSearchParams();
  const materialId = searchParams.get("material_id");
  const key = storageKey(page);

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
