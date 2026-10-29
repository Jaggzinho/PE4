from __future__ import annotations

from datetime import date

from backend.app.models.domain import ChartPanel, ChartTrace
from pe3_qc_app.db.repos.materials_repo import get_material
from pe3_qc_app.db.repos.settings_repo import get_json
from pe3_qc_app.services.chart_data import (
    durezza_tol_from_material_description,
    fetch_series,
    fetch_tolerance,
    list_fixed_chart_properties,
    tolerance_from_avg_percent,
)
from pe3_qc_app.services.material_visibility import get_visible_material_ids
from pe3_qc_app.viz.smoothing import smooth_pchip


class ChartMaterialNotFoundError(LookupError):
    pass


class ChartService:
    def _ensure_visible(self, con, *, subsidiary_id: str, material_id: int) -> None:
        visible = get_visible_material_ids(con, subsidiary_id=subsidiary_id)
        if material_id not in visible:
            raise ChartMaterialNotFoundError

    def series(
        self,
        con,
        *,
        subsidiary_id: str,
        material_id: int,
        date_from: date | None,
        date_to: date | None,
        smooth: bool,
    ) -> list[ChartTrace]:
        self._ensure_visible(con, subsidiary_id=subsidiary_id, material_id=material_id)
        traces: list[ChartTrace] = []
        for property_id, display_name, unit in list_fixed_chart_properties(con):
            if property_id is None:
                continue
            points = fetch_series(
                con,
                material_id=material_id,
                property_id=int(property_id),
                date_from=date_from,
                date_to=date_to,
            )
            x, y = self._series_values(points, smooth=smooth)
            name = f"{display_name} ({unit})" if unit else display_name
            traces.append(ChartTrace(name=name, x=x, y=y))
        return traces

    def config(self, con, *, subsidiary_id: str) -> tuple[dict, list[tuple[int | None, str, str]]]:
        # Preserve the legacy visibility seeding side effect.
        get_visible_material_ids(con, subsidiary_id=subsidiary_id)
        tolerance = get_json(con, "charts_tolerance_pct", {"warn_pct": 10.0, "alarm_pct": 20.0})
        return tolerance, list_fixed_chart_properties(con)

    def panels(
        self,
        con,
        *,
        subsidiary_id: str,
        material_id: int,
        date_from: date | None,
        date_to: date | None,
        smooth: bool,
        include_average: bool,
        include_tolerances: bool,
    ) -> list[ChartPanel]:
        self._ensure_visible(con, subsidiary_id=subsidiary_id, material_id=material_id)
        tolerance_config = get_json(
            con,
            "charts_tolerance_pct",
            {"warn_pct": 10.0, "alarm_pct": 20.0},
        )
        material = get_material(con, material_id=material_id)
        material_description = material.description if material is not None else None

        panels: list[ChartPanel] = []
        for property_id, display_name, unit in list_fixed_chart_properties(con):
            title = f"{display_name} ({unit})" if unit else display_name
            if property_id is None:
                panels.append(ChartPanel(property_id=None, title=title, unit=unit))
                continue

            points = fetch_series(
                con,
                material_id=material_id,
                property_id=int(property_id),
                date_from=date_from,
                date_to=date_to,
            )
            x, y = self._series_values(points, smooth=smooth)
            traces = [ChartTrace(name="Series", x=x, y=y)]
            average = self._average([float(point.y) for point in points])
            if include_average and x and average is not None:
                traces.append(ChartTrace(name="Average", x=x, y=[average] * len(x), kind="avg"))
            if include_tolerances and x:
                tolerance = fetch_tolerance(
                    con,
                    property_id=int(property_id),
                    material_id=material_id,
                    custom_only=True,
                )
                if tolerance is None and display_name.strip().casefold() == "durezza":
                    tolerance = durezza_tol_from_material_description(material_description)
                if tolerance is None:
                    tolerance = fetch_tolerance(
                        con,
                        property_id=int(property_id),
                        material_id=material_id,
                    )
                if tolerance is None:
                    tolerance = tolerance_from_avg_percent(
                        average,
                        warn_pct=tolerance_config.get("warn_pct"),
                        alarm_pct=tolerance_config.get("alarm_pct"),
                    )
                if tolerance is not None and tolerance.get("reference_value") is not None:
                    reference = float(tolerance["reference_value"])
                    traces.append(ChartTrace(name="Reference", x=x, y=[reference] * len(x), kind="reference"))
                traces.extend(self._tolerance_traces(x=x, tolerance=tolerance))
            panels.append(
                ChartPanel(
                    property_id=int(property_id),
                    title=title,
                    unit=unit,
                    traces=traces,
                )
            )
        return panels

    @staticmethod
    def _series_values(points, *, smooth: bool) -> tuple[list[str], list[float]]:
        dates = [point.x for point in points]
        values = [float(point.y) for point in points]
        if smooth and len(dates) >= 2:
            smoothed_dates, smoothed_values = smooth_pchip(dates, values)
            return [value.isoformat() for value in smoothed_dates], [float(value) for value in smoothed_values]
        return [value.isoformat() for value in dates], values

    @staticmethod
    def _average(values: list[float]) -> float | None:
        if not values:
            return None
        return sum(values) / len(values)

    @staticmethod
    def _tolerance_traces(*, x: list[str], tolerance: dict | None) -> list[ChartTrace]:
        if not x or tolerance is None:
            return []
        traces: list[ChartTrace] = []
        for key, label, kind in (
            ("warn_low", "Warn low", "warn"),
            ("warn_high", "Warn high", "warn"),
            ("alarm_low", "Alarm low", "alarm"),
            ("alarm_high", "Alarm high", "alarm"),
        ):
            value = tolerance.get(key)
            if value is None:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            traces.append(ChartTrace(name=label, x=x, y=[number] * len(x), kind=kind))
        return traces
