"""CLI del AI Video Automator.

Uso:
    python -m src.main new "Crea un Short sobre el próximo evento de Roblox"
    python -m src.main resume video-0001
    python -m src.main status [video-0001]
    python -m src.main batch ideas.txt --count 10
    python -m src.main process-inbox
"""
from __future__ import annotations

import argparse

from .orchestrator import Orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ai-video-automator",
        description="Idea → video corto terminado (Shorts / TikTok / Reels).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Crea un proyecto desde una idea y ejecuta el pipeline")
    p_new.add_argument("idea")
    p_new.add_argument("--template", default=None, help="Forzar plantilla (news, gaming, roblox, ...)")
    p_new.add_argument("--duration", type=int, default=None, help="Duración objetivo: 15/30/45/60 s")

    p_resume = sub.add_parser("resume", help="Reanuda un proyecto desde su último checkpoint")
    p_resume.add_argument("project_id")

    p_status = sub.add_parser("status", help="Estado de un proyecto o resumen de todos")
    p_status.add_argument("project_id", nargs="?")

    p_batch = sub.add_parser("batch", help="Genera un lote de videos con ideas diversas")
    p_batch.add_argument("source", help="Tema o archivo de ideas (una por línea)")
    p_batch.add_argument("--count", type=int, default=10)

    sub.add_parser("process-inbox", help="Convierte ideas/inbox/*.json en proyectos (Trend Agent)")

    args = parser.parse_args()
    orch = Orchestrator.from_repo_root()

    try:
        if args.command == "new":
            orch.create_and_run(args.idea, template=args.template, duration=args.duration)
        elif args.command == "resume":
            orch.resume(args.project_id)
        elif args.command == "status":
            orch.status(args.project_id)
        elif args.command == "batch":
            orch.batch(args.source, count=args.count)
        elif args.command == "process-inbox":
            orch.process_inbox()
    except KeyboardInterrupt:
        # Ctrl+C fuera del pipeline: salida limpia, sin traceback de asyncio.
        print("\ninterrumpido por el usuario (Ctrl+C)", flush=True)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
