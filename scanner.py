import argparse
import os
import shlex
import sqlite3
import subprocess
import json
import time
import signal
import re
from datetime import datetime, timedelta

from merge import HtmlGenerator


DB = "state.db"


def load_config():
    try:
        with open("config.json") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: No se encontró el archivo config.json. Asegúrate de que existe y contiene la configuración necesaria.")
        exit(1)
    except json.JSONDecodeError:
        print("Error: El archivo config.json no es un JSON válido.")
        exit(1)


def within_schedule(config):
    now = datetime.now().time()
    start = datetime.strptime(config["start_time"], "%H:%M").time()
    end = datetime.strptime(config["end_time"], "%H:%M").time()
    return start <= now <= end


def connect_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def is_database_initialized(conn):
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM batches LIMIT 1")
        return True
    except sqlite3.OperationalError:
        return False


def format_duration(seconds):
    if seconds is None:
        return "N/A"
    return str(timedelta(seconds=int(seconds)))


def get_progress_summary(conn):
    cur = conn.cursor()
    summary = {}

    summary["total_ips"] = cur.execute("SELECT COUNT(*) FROM batch_targets").fetchone()[0] or 0
    summary["total_batches"] = cur.execute("SELECT COUNT(*) FROM batches").fetchone()[0] or 0
    summary["done_batches"] = cur.execute("SELECT COUNT(*) FROM batches WHERE status='done'").fetchone()[0] or 0
    summary["pending_batches"] = cur.execute("SELECT COUNT(*) FROM batches WHERE status='pending'").fetchone()[0] or 0
    summary["in_progress_batches"] = cur.execute("SELECT COUNT(*) FROM batches WHERE status='in_progress'").fetchone()[0] or 0
    summary["completed_ips"] = cur.execute(
        "SELECT COUNT(*) FROM batch_targets WHERE batch_id IN (SELECT id FROM batches WHERE status='done')"
    ).fetchone()[0] or 0

    summary["percent_complete"] = 0.0
    if summary["total_ips"]:
        summary["percent_complete"] = round(summary["completed_ips"] / summary["total_ips"] * 100, 1)

    avg_seconds = cur.execute(
        "SELECT AVG(strftime('%s', completed_at) - strftime('%s', started_at)) FROM batches "
        "WHERE status='done' AND completed_at IS NOT NULL AND started_at IS NOT NULL"
    ).fetchone()[0]
    summary["avg_batch_seconds"] = avg_seconds
    summary["estimated_remaining"] = None
    if avg_seconds is not None:
        summary["estimated_remaining"] = avg_seconds * summary["pending_batches"]

    return summary


def print_progress(conn):
    summary = get_progress_summary(conn)
    print("=== Progreso del escaneo ===")
    print(f"Total IPs: {summary['total_ips']}")
    print(f"Total lotes: {summary['total_batches']}")
    print(f"Completados: {summary['done_batches']} | En progreso: {summary['in_progress_batches']} | Pendientes: {summary['pending_batches']}")
    print(f"Porcentaje completado: {summary['percent_complete']}%")
    print(f"Tiempo promedio por lote: {format_duration(summary['avg_batch_seconds'])}")
    print(f"ETA restante: {format_duration(summary['estimated_remaining'])}")
    print("============================")


def get_next_batch(conn):
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id FROM batches WHERE status='in_progress' ORDER BY id LIMIT 1"
    ).fetchone()
    if row:
        return row[0]
    row = cur.execute(
        "SELECT id FROM batches WHERE status='pending' ORDER BY id LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def get_batch_ips(conn, batch_id):
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT ip FROM batch_targets WHERE batch_id = ? ORDER BY id",
        (batch_id,)
    ).fetchall()
    return [row[0] for row in rows]


def update_batch_status(conn, batch_id, status, output_file=None):
    cur = conn.cursor()
    query = "UPDATE batches SET status = ?, last_update = CURRENT_TIMESTAMP"
    params = [status]

    if status == "in_progress":
        query += ", started_at = CURRENT_TIMESTAMP"
    elif status == "done":
        query += ", completed_at = CURRENT_TIMESTAMP"

    if output_file is not None:
        query += ", output_file = ?"
        params.append(output_file)

    query += " WHERE id = ?"
    params.append(batch_id)

    cur.execute(query, tuple(params))
    conn.commit()


def run_nmap(ips, config, batch_id):
    output_file = os.path.join(config["output_dir"], f"scan_{batch_id}.xml")
    cmd = ["nmap"] + shlex.split(config["nmap_args"]) + ["-oX", output_file] + ips
    process = subprocess.Popen(cmd)
    return process, output_file


def init_database(config):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.executescript(
        "PRAGMA foreign_keys = ON;"
        "DROP TABLE IF EXISTS batch_targets;"
        "DROP TABLE IF EXISTS batches;"
        "DROP TABLE IF EXISTS targets;"
        "CREATE TABLE batches ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " status TEXT NOT NULL DEFAULT 'pending',"
        " created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
        " started_at TIMESTAMP,"
        " completed_at TIMESTAMP,"
        " last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
        " output_file TEXT"
        ");"
        "CREATE TABLE batch_targets ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " batch_id INTEGER NOT NULL,"
        " ip TEXT NOT NULL,"
        " FOREIGN KEY(batch_id) REFERENCES batches(id) ON DELETE CASCADE"
        ");"
    )

    with open("targets.txt") as f:
        ips = [line.strip() for line in f if line.strip()]

    for i in range(0, len(ips), config["batch_size"]):
        cur.execute("INSERT INTO batches(status) VALUES('pending')")
        batch_id = cur.lastrowid
        batch_ips = ips[i : i + config["batch_size"]]
        cur.executemany(
            "INSERT INTO batch_targets(batch_id, ip) VALUES(?, ?)",
            [(batch_id, ip) for ip in batch_ips],
        )

    conn.commit()
    conn.close()
    print(f"Base de datos inicializada con {len(ips)} IPs divididas en {((len(ips) + config['batch_size'] - 1) // config['batch_size'])} lotes.")


def run_scan(config):
    if not os.path.exists(config["output_dir"]):
        os.makedirs(config["output_dir"], exist_ok=True)

    conn = connect_db()
    if not is_database_initialized(conn):
        print("Error: La base de datos no está inicializada. Ejecuta 'python scanner.py init' primero.")
        conn.close()
        return

    print_progress(conn)

    while True:
        if not within_schedule(config):
            print("Fuera de horario. Deteniendo el escaneo hasta la próxima ventana horaria.")
            conn.close()
            return

        batch_id = get_next_batch(conn)
        if batch_id is None:
            print("No hay más lotes pendientes o en progreso. Escaneo completado.")
            conn.close()
            return

        ips = get_batch_ips(conn, batch_id)
        print(f"Iniciando lote {batch_id} con {len(ips)} IPs...")
        update_batch_status(conn, batch_id, "in_progress")

        process, output_file = run_nmap(ips, config, batch_id)
        update_batch_status(conn, batch_id, "in_progress", output_file=output_file)

        try:
            while True:
                if process.poll() is not None:
                    print(f"Lote {batch_id} completado.")
                    update_batch_status(conn, batch_id, "done")
                    break

                if not within_schedule(config):
                    print("Fuera de horario, parando el escaneo y marcando el lote como pendiente para reanudación futura.")
                    process.send_signal(signal.SIGINT)
                    update_batch_status(conn, batch_id, "pending", output_file=output_file)
                    conn.close()
                    return

                time.sleep(config.get("check_interval_in_seconds", 5))

        except KeyboardInterrupt:
            print("Interrupción manual. Terminando proceso y dejando el lote como pendiente.")
            process.terminate()
            update_batch_status(conn, batch_id, "pending", output_file=output_file)
            conn.close()
            return

        print_progress(conn)  # Print progress after each batch


def main():
    parser = argparse.ArgumentParser(description="Escaneo Nmap por lotes con estado persistente y ventana horaria")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Inicializar la base de datos y crear lotes desde targets.txt")
    subparsers.add_parser("status", help="Mostrar resumen y progreso de los lotes")
    subparsers.add_parser("run", help="Ejecutar el siguiente lote pendiente o reanudar un lote en progreso")
    subparsers.add_parser("html", help="Fusionar XMLs y generar reporte HTML")

    args = parser.parse_args()
    config = load_config()

    if args.command == "init":
        init_database(config)
    elif args.command == "status":
        conn = connect_db()
        if not is_database_initialized(conn):
            print("Error: La base de datos no está inicializada. Ejecuta 'python scanner.py init' primero.")
            conn.close()
            return
        print_progress(conn)
        conn.close()
    elif args.command == "html":
            generator = HtmlGenerator(output_dir=config["output_dir"])
            generator.generate_html_report()
    else:
        run_scan(config)


if __name__ == "__main__":
    main()
