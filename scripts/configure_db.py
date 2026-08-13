#!/usr/bin/env python3
"""Настройка базы OpenWebUI под «Учебный ассистент».

Применяет к webui.db всё, что не задаётся переменными окружения:
права обычных пользователей, модель по умолчанию и её публичный доступ,
карточки-подсказки, общие промпты учителя.

Запуск (контейнер должен быть ОСТАНОВЛЕН, чтобы база не была занята):

    docker compose stop openwebui
    sudo python3 scripts/configure_db.py
    docker compose start openwebui

Ключ ProxyAPI скрипт берёт из .env (OPENAI_API_KEY) рядом с docker-compose.yml.
Скрипт идемпотентен — можно запускать повторно.
"""
import json
import os
import sqlite3
import sys
import time
import uuid

DB = os.environ.get(
    "WEBUI_DB", "/var/lib/docker/volumes/openwebui_open-webui/_data/webui.db"
)
SEED = os.path.join(os.path.dirname(__file__), "seed-data.json")
ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")


def read_env_key(name):
    if os.environ.get(name):
        return os.environ[name]
    try:
        for line in open(ENV_FILE):
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return None


def main():
    seed = json.load(open(SEED))
    api_key = read_env_key("OPENAI_API_KEY")
    if not api_key:
        sys.exit("OPENAI_API_KEY не найден ни в окружении, ни в .env")

    con = sqlite3.connect(DB)
    now = int(time.time())

    # первый зарегистрированный админ станет владельцем записей
    admin = con.execute(
        "SELECT id FROM user WHERE role='admin' ORDER BY created_at LIMIT 1"
    ).fetchone()
    if not admin:
        sys.exit("В базе нет администратора — сначала зарегистрируйте первый аккаунт")
    admin_id = admin[0]

    # --- config (PersistentConfig живёт в базе, env игнорируется после первого старта) ---
    config = dict(seed["config"])
    config["openai.api_keys"] = [api_key]
    for key, value in config.items():
        row = con.execute("SELECT 1 FROM config WHERE key=?", (key,)).fetchone()
        if row:
            con.execute(
                "UPDATE config SET value=?, updated_at=? WHERE key=?",
                (json.dumps(value, ensure_ascii=False), now, key),
            )
        else:
            con.execute(
                "INSERT INTO config (key, value, updated_at) VALUES (?,?,?)",
                (key, json.dumps(value, ensure_ascii=False), now),
            )

    # --- запись модели + публичный доступ ---
    m = seed["model"]
    con.execute(
        "INSERT OR REPLACE INTO model (id, user_id, base_model_id, name, params, meta, updated_at, created_at, is_active) "
        "VALUES (?,?,NULL,?,?,?,?,?,1)",
        (m["id"], admin_id, m["name"], json.dumps(m["params"]),
         json.dumps(m["meta"]), now, now),
    )
    grant_public(con, "model", m["id"], now)

    # --- общие промпты ---
    for p in seed["prompts"]:
        row = con.execute(
            "SELECT id FROM prompt WHERE command=?", (p["command"],)
        ).fetchone()
        if row:
            pid = row[0]
            con.execute(
                "UPDATE prompt SET name=?, content=?, updated_at=? WHERE id=?",
                (p["name"], p["content"], now, pid),
            )
        else:
            pid = str(uuid.uuid4())
            con.execute(
                "INSERT INTO prompt (id, command, user_id, name, content, tags, is_active, created_at, updated_at) "
                "VALUES (?,?,?,?,?,'[]',1,?,?)",
                (pid, p["command"], admin_id, p["name"], p["content"], now, now),
            )
        # tags не может быть NULL — иначе /api/v1/prompts падает с 500
        con.execute("UPDATE prompt SET tags='[]' WHERE id=? AND tags IS NULL", (pid,))
        grant_public(con, "prompt", pid, now)

    # --- гейт учебных запросов (filter-функция, срабатывает до обращения к LLM) ---
    gate_code = open(os.path.join(os.path.dirname(__file__), "mes-gate.py")).read()
    gate_meta = json.dumps(
        {"description": "Отклоняет неучебные запросы до обращения к LLM", "manifest": {}},
        ensure_ascii=False,
    )
    if con.execute("SELECT 1 FROM function WHERE id='mes_gate'").fetchone():
        con.execute(
            "UPDATE function SET content=?, meta=?, is_active=1, is_global=1, updated_at=? WHERE id='mes_gate'",
            (gate_code, gate_meta, now),
        )
    else:
        con.execute(
            "INSERT INTO function (id, user_id, name, type, content, meta, valves, is_active, is_global, updated_at, created_at) "
            "VALUES ('mes_gate', ?, 'МЭШ-гейт учебных запросов', 'filter', ?, ?, NULL, 1, 1, ?, ?)",
            (admin_id, gate_code, gate_meta, now, now),
        )

    con.commit()
    print("Готово: config —", len(config), "ключей; модель —", m["id"],
          "; промптов —", len(seed["prompts"]), "; гейт mes_gate установлен")


def grant_public(con, rtype, rid, now):
    """Публичный доступ на чтение = principal_type='user', principal_id='*'."""
    con.execute(
        "INSERT OR IGNORE INTO access_grant (id, resource_type, resource_id, principal_type, principal_id, permission, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), rtype, rid, "user", "*", "read", now),
    )


if __name__ == "__main__":
    main()
