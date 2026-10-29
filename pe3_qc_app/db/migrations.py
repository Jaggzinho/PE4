from __future__ import annotations

import json


def apply_migrations(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version(
            version INTEGER NOT NULL
        )
        """
    )
    row = con.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if row is None:
        con.execute("INSERT INTO schema_version(version) VALUES (0)")
        version = 0
    else:
        version = int(row[0])

    migrations = [
        (1, _m001_init),
        (2, _m002_indexes),
        (3, _m003_test_component_lots),
        (4, _m004_lastrine_notify_template),
        (5, _m005_charts_tolerance_pct_setting),
        (6, _m006_components_master_data),
        (7, _m007_i18n_locales),
        (8, _m008_sample_request_queue),
        (9, _m009_rating_system),
        (10, _m010_prod_date_indexes),
        (11, _m011_import_jobs),
        (12, _m012_tolerance_inputs),
        (13, _m013_tolerance_origin),
    ]

    for v, fn in migrations:
        if version >= v:
            continue
        fn(con)
        con.execute("UPDATE schema_version SET version = ?", [v])
        version = v


def _m011_import_jobs(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS import_jobs (
            job_id TEXT PRIMARY KEY,
            owner_id BIGINT NOT NULL,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            progress INTEGER NOT NULL,
            messages_json TEXT NOT NULL,
            result_json TEXT,
            error TEXT,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_import_jobs_owner_created ON import_jobs(owner_id, created_at)")


def _m012_tolerance_inputs(con) -> None:
    con.execute("ALTER TABLE tolerances ADD COLUMN IF NOT EXISTS reference_value DOUBLE")
    for bound in ("warn_low", "warn_high", "alarm_low", "alarm_high"):
        con.execute(f"ALTER TABLE tolerances ADD COLUMN IF NOT EXISTS {bound}_input DOUBLE")
        con.execute(f"ALTER TABLE tolerances ADD COLUMN IF NOT EXISTS {bound}_mode VARCHAR")
        con.execute(
            f"UPDATE tolerances SET {bound}_input = {bound}, {bound}_mode = 'absolute' "
            f"WHERE {bound}_mode IS NULL AND {bound} IS NOT NULL"
        )


def _m013_tolerance_origin(con) -> None:
    con.execute("ALTER TABLE tolerances ADD COLUMN IF NOT EXISTS is_custom BOOLEAN")
    # Preserve user-entered reference/percentage limits saved by the v12 web editor.
    con.execute("""
        UPDATE tolerances SET is_custom = TRUE
        WHERE reference_value IS NOT NULL
           OR warn_low_mode = 'percent' OR warn_high_mode = 'percent'
           OR alarm_low_mode = 'percent' OR alarm_high_mode = 'percent'
    """)


def _m001_init(con) -> None:
    con.execute(
        """
        CREATE TABLE roles(
            role_id BIGINT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            can_edit_master BOOLEAN NOT NULL,
            can_edit_tests BOOLEAN NOT NULL,
            can_manage_users BOOLEAN NOT NULL,
            can_send_outlook BOOLEAN NOT NULL
        );

        CREATE TABLE users(
            user_id BIGINT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            pw_salt BLOB NOT NULL,
            pw_hash BLOB NOT NULL,
            role_id BIGINT NOT NULL REFERENCES roles(role_id),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL,
            last_login_at TIMESTAMP
        );

        CREATE TABLE settings(
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL
        );

        CREATE TABLE materials(
            material_id BIGINT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            description TEXT,
            lastrina_code TEXT,
            lastrina_desc TEXT,
            system_name TEXT,
            machine_name TEXT,
            active BOOLEAN NOT NULL DEFAULT TRUE
        );

        CREATE TABLE properties(
            property_id BIGINT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            unit TEXT,
            data_type TEXT NOT NULL DEFAULT 'num',
            active BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order INTEGER
        );

        CREATE TABLE tolerances(
            tolerance_id BIGINT PRIMARY KEY,
            material_id BIGINT REFERENCES materials(material_id),
            property_id BIGINT NOT NULL REFERENCES properties(property_id),
            warn_low DOUBLE,
            warn_high DOUBLE,
            alarm_low DOUBLE,
            alarm_high DOUBLE,
            updated_at TIMESTAMP NOT NULL
        );

        CREATE TABLE tests(
            test_id BIGINT PRIMARY KEY,
            material_id BIGINT NOT NULL REFERENCES materials(material_id),
            request_date DATE,
            prod_date DATE,
            analysis_date DATE,
            notes TEXT,
            created_by BIGINT REFERENCES users(user_id),
            created_at TIMESTAMP NOT NULL,
            deleted_at TIMESTAMP,
            external_source TEXT,
            external_row_key TEXT
        );

        CREATE TABLE measurements(
            measurement_id BIGINT PRIMARY KEY,
            test_id BIGINT NOT NULL REFERENCES tests(test_id),
            property_id BIGINT NOT NULL REFERENCES properties(property_id),
            value_num DOUBLE,
            value_text TEXT
        );

        CREATE TABLE sinottico_items(
            item_id BIGINT PRIMARY KEY,
            machine_code TEXT,
            excel_label TEXT,
            excel_code TEXT,
            description TEXT,
            material_id BIGINT REFERENCES materials(material_id),
            sort_order INTEGER,
            active BOOLEAN NOT NULL DEFAULT TRUE
        );

        CREATE TABLE contacts(
            contact_id BIGINT PRIMARY KEY,
            name TEXT,
            email TEXT NOT NULL,
            group_name TEXT NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE
        );

        CREATE TABLE email_templates(
            template_id BIGINT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            to_group TEXT,
            cc_group TEXT,
            subject_tmpl TEXT NOT NULL,
            body_tmpl TEXT NOT NULL,
            is_html BOOLEAN NOT NULL DEFAULT FALSE,
            active BOOLEAN NOT NULL DEFAULT TRUE
        );

        CREATE TABLE sample_requests(
            req_id BIGINT PRIMARY KEY,
            item_id BIGINT NOT NULL REFERENCES sinottico_items(item_id),
            requested_at TIMESTAMP NOT NULL,
            requested_by BIGINT REFERENCES users(user_id),
            outcome TEXT NOT NULL,
            subject TEXT,
            to_list TEXT,
            cc_list TEXT
        );
        """
    )

    from pe3_qc_app.services.time_utils import utc_now_naive

    now = utc_now_naive().isoformat(sep=" ", timespec="seconds")
    con.execute(
        """
        INSERT INTO roles(role_id, name, can_edit_master, can_edit_tests, can_manage_users, can_send_outlook)
        VALUES
            (1, 'Admin', TRUE, TRUE, TRUE, TRUE),
            (2, 'ReadOnly', FALSE, FALSE, FALSE, TRUE)
        ON CONFLICT(name) DO NOTHING
        """
    )
    con.execute(
        "INSERT INTO settings(key, value_json) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
        ["sinottico_thresholds", json.dumps({"green_days": 90, "yellow_days": 180})],
    )
    con.execute(
        "INSERT INTO settings(key, value_json) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
        ["theme", json.dumps({"mode": "light"})],
    )
    con.execute(
        """
        INSERT INTO email_templates(template_id, name, to_group, cc_group, subject_tmpl, body_tmpl, is_html, active)
        VALUES
        (
            1,
            'Default Sample Request',
            'QC',
            NULL,
            'Sample request {machine_code} - {material_code}',
            'Richiesta campionatura\\n\\nMAC: {machine_code}\\nMateriale: {material_code}\\nDescrizione: {material_desc}\\nLastrina: {lastrina_code}\\nUltima richiesta: {last_request_date}\\nGiorni: {days_since}\\nData: {today}\\n',
            FALSE,
            TRUE
        )
        ON CONFLICT(name) DO NOTHING
        """
    )
    con.execute(
        """
        INSERT INTO settings(key, value_json) VALUES (?, ?) ON CONFLICT(key) DO NOTHING
        """,
        ["created_at_utc", json.dumps({"created_at": now})],
    )


def _m002_indexes(con) -> None:
    con.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_tests_ext ON tests(external_source, external_row_key);
        CREATE INDEX IF NOT EXISTS ix_tests_mat_req ON tests(material_id, request_date);
        CREATE INDEX IF NOT EXISTS ix_meas_test ON measurements(test_id);
        CREATE INDEX IF NOT EXISTS ix_tol_prop_mat ON tolerances(property_id, material_id);
        CREATE INDEX IF NOT EXISTS ix_sin_item_mat ON sinottico_items(material_id);
        """
    )


def _m005_charts_tolerance_pct_setting(con) -> None:
    con.execute(
        "INSERT INTO settings(key, value_json) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
        ["charts_tolerance_pct", json.dumps({"warn_pct": 10.0, "alarm_pct": 20.0})],
    )


def _m003_test_component_lots(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS test_component_lots(
            test_id BIGINT NOT NULL REFERENCES tests(test_id),
            type_name TEXT NOT NULL,
            component_code TEXT,
            component_desc TEXT,
            lot_code TEXT,
            PRIMARY KEY(test_id, type_name)
        );
        CREATE INDEX IF NOT EXISTS ix_tcl_test ON test_component_lots(test_id);
        """
    )


def _m004_lastrine_notify_template(con) -> None:
    # Add a second editable template to mimic the legacy Auto_Close summary mail.
    body = (
        "Buongiorno a tutti,\n\n"
        "desidero informarvi che è stata registrata una nuova richiesta di lastrine in poliuretano per TCM Romania tramite il modulo dedicato.\n\n"
        "Di seguito i dettagli della richiesta:\n"
        "* Nome del richiedente: {requester_name}\n"
        "{material_details}\n"
        "Vi invitiamo a prendere visione della richiesta e a procedere con le operazioni necessarie per la preparazione e la successiva conferma della disponibilità del materiale.\n"
        "Per qualsiasi chiarimento o integrazione, vi preghiamo di fare riferimento direttamente al richiedente.\n\n"
        "Grazie\n"
        "Cordiali saluti!\n\n"
        "-------------------------------------------\n\n"
        "Good morning everyone,\n\n"
        "I would like to inform you that a new request for polyurethane plates has been registered for TCM Romania through the dedicated form.\n\n"
        "Below are the details of the request:\n"
        "* Requester name: {requester_name}\n"
        "{material_details}\n"
        "We invite you to review the request and proceed with the necessary operations for preparation and subsequent confirmation of material availability.\n"
        "For any clarification or additional information, please contact the requester directly.\n\n"
        "Thank you\n"
        "Best regards!\n"
    )
    con.execute(
        """
        INSERT INTO email_templates(template_id, name, to_group, cc_group, subject_tmpl, body_tmpl, is_html, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO NOTHING
        """,
        [2, "Lastrine Notification", "QC", None, "Richiesta Lastrine Colata", body, False, True],
    )

    con.execute(
        "INSERT INTO settings(key, value_json) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
        ["lastrine_default_qty", json.dumps({"qty": 5})],
    )


def _m008_sample_request_queue(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS sample_request_queue(
            queue_id BIGINT PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            item_id BIGINT NOT NULL REFERENCES sinottico_items(item_id),
            added_at TIMESTAMP NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_sr_queue_user_item ON sample_request_queue(user_id, item_id);
        CREATE INDEX IF NOT EXISTS ix_sr_queue_user ON sample_request_queue(user_id);
        """
    )

    con.execute(
        """
        INSERT INTO email_templates(template_id, name, to_group, cc_group, subject_tmpl, body_tmpl, is_html, active)
        VALUES
        (
            8001,
            'Queued Sample Request (it_IT)',
            'QC',
            NULL,
            'Richiesta campionatura ({today})',
            'Buongiorno,\\n\\nRichiedente: {requester_name}\\nData: {today}\\n\\nMateriali in richiesta:\\n{material_details}\\n',
            FALSE,
            TRUE
        ),
        (
            8002,
            'Queued Sample Request (ro_RO)',
            'QC',
            NULL,
            'Cerere mostre ({today})',
            'Bună ziua,\\n\\nSolicitant: {requester_name}\\nData: {today}\\n\\nMateriale solicitate:\\n{material_details}\\n',
            FALSE,
            TRUE
        )
        ON CONFLICT(name) DO NOTHING
        """
    )


def _m009_rating_system(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS rating_property_weights(
            property_id BIGINT PRIMARY KEY REFERENCES properties(property_id),
            weight DOUBLE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rating_property_rules(
            property_id BIGINT PRIMARY KEY REFERENCES properties(property_id),
            rule_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS ix_rating_weights_prop ON rating_property_weights(property_id);
        CREATE INDEX IF NOT EXISTS ix_rating_rules_prop ON rating_property_rules(property_id);
        """
    )


def _m010_prod_date_indexes(con) -> None:
    con.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_tests_mat_prod ON tests(material_id, prod_date);
        CREATE INDEX IF NOT EXISTS ix_tests_prod ON tests(prod_date);
        """
    )


def _m006_components_master_data(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS component_types(
            type_id BIGINT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            slot_key TEXT UNIQUE,
            active BOOLEAN NOT NULL DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS components(
            component_id BIGINT PRIMARY KEY,
            type_id BIGINT NOT NULL REFERENCES component_types(type_id),
            code TEXT NOT NULL UNIQUE,
            description TEXT,
            unit TEXT,
            active BOOLEAN NOT NULL DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS material_component_defaults(
            material_id BIGINT NOT NULL REFERENCES materials(material_id),
            slot_key TEXT NOT NULL,
            component_id BIGINT NOT NULL REFERENCES components(component_id),
            PRIMARY KEY(material_id, slot_key)
        );

        CREATE INDEX IF NOT EXISTS ix_components_type ON components(type_id);
        CREATE INDEX IF NOT EXISTS ix_mcd_material ON material_component_defaults(material_id);
        """
    )


def _m007_i18n_locales(con) -> None:
    from pe3_qc_app.db.ids import new_id

    con.execute(
        "INSERT INTO settings(key, value_json) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
        ["ui_language", json.dumps({"code": "it_IT"})],
    )

    sample_subject_it = "Richiesta campione {machine_code} - {material_code}"
    sample_body_it = (
        "Richiesta campionatura\n\n"
        "MAC: {machine_code}\n"
        "Materiale: {material_code}\n"
        "Descrizione: {material_desc}\n"
        "Lastrina: {lastrina_code}\n"
        "Ultima richiesta: {last_request_date}\n"
        "Giorni: {days_since}\n"
        "Data: {today}\n"
    )
    sample_subject_ro = "Cerere eșantion {machine_code} - {material_code}"
    sample_body_ro = (
        "Cerere de eșantionare\n\n"
        "MAC: {machine_code}\n"
        "Material: {material_code}\n"
        "Descriere: {material_desc}\n"
        "Plăcuță: {lastrina_code}\n"
        "Ultima cerere: {last_request_date}\n"
        "Zile: {days_since}\n"
        "Data: {today}\n"
    )
    sample_subject_zh = "样品申请 {machine_code} - {material_code}"
    sample_body_zh = (
        "样品申请\n\n"
        "MAC: {machine_code}\n"
        "材料代码: {material_code}\n"
        "描述: {material_desc}\n"
        "板号: {lastrina_code}\n"
        "上次申请: {last_request_date}\n"
        "天数: {days_since}\n"
        "日期: {today}\n"
    )

    lastrine_subject_it = "Richiesta lastrine colata"
    lastrine_body_it = (
        "Buongiorno a tutti,\n\n"
        "desidero informarvi che è stata registrata una nuova richiesta di lastrine in poliuretano.\n\n"
        "Di seguito i dettagli della richiesta:\n"
        "* Nome del richiedente: {requester_name}\n"
        "{material_details}\n\n"
        "Vi invitiamo a prendere visione della richiesta e a procedere con le operazioni necessarie per la preparazione "
        "e la successiva conferma della disponibilità del materiale.\n"
        "Per qualsiasi chiarimento o integrazione, vi preghiamo di fare riferimento direttamente al richiedente.\n\n"
        "Grazie\n"
        "Cordiali saluti!\n"
    )

    lastrine_subject_ro = "Cerere plăcuțe poliuretan"
    lastrine_body_ro = (
        "Bună dimineața tuturor,\n\n"
        "dorim să vă informăm că a fost înregistrată o nouă cerere de plăcuțe din poliuretan.\n\n"
        "Detaliile cererii:\n"
        "* Nume solicitant: {requester_name}\n"
        "{material_details}\n\n"
        "Vă rugăm să analizați cererea și să continuați cu operațiunile necesare pentru pregătire și confirmarea "
        "ulterioară a disponibilității materialului.\n"
        "Pentru orice clarificări sau informații suplimentare, vă rugăm să contactați direct solicitantul.\n\n"
        "Mulțumim,\n"
        "Cu stimă!\n"
    )

    lastrine_subject_zh = "聚氨酯板请求"
    lastrine_body_zh = (
        "大家早上好，\n\n"
        "现通知：已登记一条新的聚氨酯板（lastrine）请求。\n\n"
        "请求详情：\n"
        "* 申请人：{requester_name}\n"
        "{material_details}\n\n"
        "请查阅该请求并进行必要操作，以便准备并后续确认材料可用性。\n"
        "如需澄清或补充信息，请直接联系申请人。\n\n"
        "谢谢！\n"
        "此致\n"
    )

    templates = [
        ("Default Sample Request (it_IT)", "QC", None, sample_subject_it, sample_body_it),
        ("Default Sample Request (ro_RO)", "QC", None, sample_subject_ro, sample_body_ro),
        ("Default Sample Request (zh_CN)", "QC", None, sample_subject_zh, sample_body_zh),
        ("Lastrine Notification (it_IT)", "QC", None, lastrine_subject_it, lastrine_body_it),
        ("Lastrine Notification (ro_RO)", "QC", None, lastrine_subject_ro, lastrine_body_ro),
        ("Lastrine Notification (zh_CN)", "QC", None, lastrine_subject_zh, lastrine_body_zh),
    ]
    for name, to_group, cc_group, subject_tmpl, body_tmpl in templates:
        con.execute(
            """
            INSERT INTO email_templates(template_id, name, to_group, cc_group, subject_tmpl, body_tmpl, is_html, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO NOTHING
            """,
            [new_id(), name, to_group, cc_group, subject_tmpl, body_tmpl, False, True],
        )
