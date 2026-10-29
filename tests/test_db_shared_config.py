from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pe3_qc_app.core import local_config
from pe3_qc_app.core.paths import AppPaths, allow_missing_db_autocreate, resolve_paths


class TestDbSharedConfig(unittest.TestCase):
    def test_config_save_load_and_clear_db_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            programdata = Path(td) / "ProgramData"
            localappdata = Path(td) / "LocalAppData"
            programdata.mkdir(parents=True, exist_ok=True)
            localappdata.mkdir(parents=True, exist_ok=True)

            with patch.dict(
                os.environ,
                {"PROGRAMDATA": str(programdata), "LOCALAPPDATA": str(localappdata)},
                clear=False,
            ):
                # Save
                dbp = Path(td) / "share" / "qc.duckdb"
                local_config.set_db_path_override(dbp)
                self.assertEqual(local_config.get_db_path_override(), str(dbp))

                # Clear
                local_config.set_db_path_override(None)
                self.assertIsNone(local_config.get_db_path_override())

    def test_config_dir_falls_back_when_programdata_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            localappdata = Path(td) / "LocalAppData"
            localappdata.mkdir(parents=True, exist_ok=True)
            with patch.dict(
                os.environ,
                # "?:\\bad" should fail on Windows path resolution/mkdir.
                {"PROGRAMDATA": "?:\\bad", "LOCALAPPDATA": str(localappdata)},
                clear=False,
            ):
                p = local_config.get_config_dir()
                self.assertTrue(str(p).lower().endswith("\\pe3"))
                self.assertIn(str(localappdata).lower(), str(p).lower())

    def test_resolve_paths_precedence_cli_over_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            local = Path(td) / "Local"
            local.mkdir(parents=True, exist_ok=True)
            with patch("pe3_qc_app.core.paths._is_writable_dir", return_value=False), patch(
                "pe3_qc_app.core.paths._local_appdata_dir", return_value=local
            ), patch(
                "pe3_qc_app.core.local_config.get_db_path_override_for",
                return_value=str(Path(td) / "cfg.duckdb"),
            ), patch(
                "pe3_qc_app.core.local_config.get_db_distribution_for",
                return_value=None,
            ):
                paths = resolve_paths(db_override=str(Path(td) / "cli.duckdb"), subsidiary_id="tcm_ro")
                self.assertEqual(paths.db_source, "cli")
                self.assertTrue(str(paths.db_path).endswith("cli.duckdb"))

    def test_resolve_paths_precedence_config_over_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            local = Path(td) / "Local"
            local.mkdir(parents=True, exist_ok=True)
            with patch("pe3_qc_app.core.paths._is_writable_dir", return_value=False), patch(
                "pe3_qc_app.core.paths._local_appdata_dir", return_value=local
            ), patch(
                "pe3_qc_app.core.local_config.get_db_path_override_for",
                return_value=str(Path(td) / "cfg.duckdb"),
            ), patch(
                "pe3_qc_app.core.local_config.get_db_distribution_for",
                return_value=None,
            ):
                paths = resolve_paths(db_override=None, subsidiary_id="tcm_ro")
                self.assertEqual(paths.db_source, "config")
                self.assertTrue(str(paths.db_path).endswith("cfg.duckdb"))

    def test_distribution_config_save_load_and_clear(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            programdata = Path(td) / "ProgramData"
            localappdata = Path(td) / "LocalAppData"
            programdata.mkdir(parents=True, exist_ok=True)
            localappdata.mkdir(parents=True, exist_ok=True)

            with patch.dict(
                os.environ,
                {"PROGRAMDATA": str(programdata), "LOCALAPPDATA": str(localappdata)},
                clear=False,
            ):
                sid = "tcm_ro"
                source = Path(td) / "OneDrive" / "PE3" / "qc_tcm_ro_ro.duckdb"
                local_config.set_db_distribution_for(subsidiary_id=sid, mode="onedrive_sync", source_path=source)
                dist = local_config.get_db_distribution_for(subsidiary_id=sid)
                self.assertIsNotNone(dist)
                assert dist is not None
                self.assertEqual(dist.get("mode"), "onedrive_sync")
                self.assertEqual(dist.get("source_path"), str(source))

                local_config.set_db_distribution_for(subsidiary_id=sid, mode=None, source_path=None)
                self.assertIsNone(local_config.get_db_distribution_for(subsidiary_id=sid))

    def test_distribution_config_rejects_url_like_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            programdata = Path(td) / "ProgramData"
            localappdata = Path(td) / "LocalAppData"
            programdata.mkdir(parents=True, exist_ok=True)
            localappdata.mkdir(parents=True, exist_ok=True)

            with patch.dict(
                os.environ,
                {"PROGRAMDATA": str(programdata), "LOCALAPPDATA": str(localappdata)},
                clear=False,
            ):
                sid = "tcm_ro"
                url = "https://wamgroupcloud-my.sharepoint.com/:u:/r/personal/x/Documents/qc.duckdb"
                local_config.set_db_distribution_for(subsidiary_id=sid, mode="onedrive_sync", source_path=Path(url))
                self.assertIsNone(local_config.get_db_distribution_for(subsidiary_id=sid))

    def test_resolve_paths_uses_distribution_cache_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "Data"
            data_dir.mkdir(parents=True, exist_ok=True)
            source_dir = Path(td) / "OneDrive" / "PE3"
            source_dir.mkdir(parents=True, exist_ok=True)
            source = source_dir / "qc_tcm_ro_ro.duckdb"
            source.write_bytes(b"duckdb-snapshot")

            with patch("pe3_qc_app.core.paths._is_writable_dir", return_value=False), patch(
                "pe3_qc_app.core.paths._local_appdata_dir", return_value=data_dir.parent
            ), patch(
                "pe3_qc_app.core.local_config.get_db_distribution_for",
                return_value={"mode": "onedrive_sync", "source_path": str(source)},
            ), patch(
                "pe3_qc_app.core.local_config.get_db_path_override_for",
                return_value=None,
            ):
                paths = resolve_paths(db_override=None, subsidiary_id="tcm_ro")
                self.assertEqual(paths.db_source, "distribution_cache")
                self.assertIn(str(data_dir.parent).lower(), str(paths.data_dir).lower())
                self.assertTrue(paths.db_path.exists())

    def test_resolve_paths_distribution_falls_back_to_cached(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            data_dir_parent = Path(td) / "Local"
            data_dir_parent.mkdir(parents=True, exist_ok=True)
            # resolve_paths uses _local_appdata_dir()/PE3 as data_dir when app_dir isn't writable.
            cache_dir = data_dir_parent / "PE3" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cached = cache_dir / "qc_tcm_ro_ro.duckdb"
            cached.write_bytes(b"cached")

            missing_source = Path(td) / "OneDrive" / "PE3" / "qc_tcm_ro_ro.duckdb"
            with patch("pe3_qc_app.core.paths._is_writable_dir", return_value=False), patch(
                "pe3_qc_app.core.paths._local_appdata_dir", return_value=data_dir_parent
            ), patch(
                "pe3_qc_app.core.local_config.get_db_distribution_for",
                return_value={"mode": "onedrive_sync", "source_path": str(missing_source)},
            ), patch(
                "pe3_qc_app.core.local_config.get_db_path_override_for",
                return_value=None,
            ):
                paths = resolve_paths(db_override=None, subsidiary_id="tcm_ro")
                self.assertEqual(paths.db_source, "distribution_cache")
                self.assertEqual(paths.db_path, cached)
                self.assertTrue(paths.db_path.exists())

    def test_allow_missing_db_autocreate_tcm_ro_config_inside_data_dir(self) -> None:
        p = AppPaths(
            app_dir=Path(r"C:\Apps\PE3"),
            data_dir=Path(r"C:\Apps\PE3"),
            db_path=Path(r"C:\Apps\PE3\qc.duckdb"),
            db_source="config",
            subsidiary_id="tcm_ro",
        )
        self.assertTrue(allow_missing_db_autocreate(p))

    def test_allow_missing_db_autocreate_rejects_other_subsidiary(self) -> None:
        p = AppPaths(
            app_dir=Path(r"C:\Apps\PE3"),
            data_dir=Path(r"C:\Apps\PE3"),
            db_path=Path(r"C:\Apps\PE3\qc.duckdb"),
            db_source="config",
            subsidiary_id="wam_ro",
        )
        self.assertFalse(allow_missing_db_autocreate(p))

    def test_allow_missing_db_autocreate_rejects_unc(self) -> None:
        p = AppPaths(
            app_dir=Path(r"C:\Apps\PE3"),
            data_dir=Path(r"C:\Apps\PE3"),
            db_path=Path(r"\\server\share\qc.duckdb"),
            db_source="config",
            subsidiary_id="tcm_ro",
        )
        self.assertFalse(allow_missing_db_autocreate(p))

    def test_allow_missing_db_autocreate_rejects_outside_data_dir(self) -> None:
        p = AppPaths(
            app_dir=Path(r"C:\Apps\PE3"),
            data_dir=Path(r"C:\Apps\PE3"),
            db_path=Path(r"C:\Other\qc.duckdb"),
            db_source="config",
            subsidiary_id="tcm_ro",
        )
        self.assertFalse(allow_missing_db_autocreate(p))


if __name__ == "__main__":
    unittest.main()
