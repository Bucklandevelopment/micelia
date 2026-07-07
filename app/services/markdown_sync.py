"""
MarkdownSyncService: Sincronizacion bidireccional DB <-> Markdown files.

Mantiene en sync:
- PromptListModel (DB) <-> data/prompt-lists/*.md
- Captured prompts (DB) -> data/prompt-inbox/YYYY/MM/YYYY-MM-DD.md
- Archived prompts (DB) -> data/prompt-archives/YYYY/MM.md

Background task que ejecuta sync cada 60 segundos.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.logging import log
from app.core.time import utcnow_naive
from app.services.prompt_store import PromptStore


class MarkdownSyncService:
    """Sincronizacion bidireccional DB <-> Markdown files"""

    def __init__(self, prompt_store: PromptStore):
        self.prompt_store = prompt_store
        self._base_dir = Path(__file__).resolve().parent.parent.parent / "data"
        self.lists_dir = str(self._base_dir / "prompt-lists")
        self.inbox_dir = str(self._base_dir / "prompt-inbox")
        self.archive_dir = str(self._base_dir / "prompt-archives")

        self._task: Optional[asyncio.Task] = None
        self.running = False
        self.interval = 60  # seconds
        self.last_sync: Optional[datetime] = None
        self.last_sync_result: Optional[dict] = None
        self.sync_count = 0

    # ================================================================
    # Lifecycle
    # ================================================================

    async def start(self):
        """Inicia sync periodico como background task (every 60s)"""
        if self._task and not self._task.done():
            return
        self._ensure_dirs()
        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        log.info(f"MarkdownSyncService iniciado (intervalo: {self.interval}s)")

    async def stop(self):
        """Detiene sync"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("MarkdownSyncService detenido")

    async def _run_loop(self):
        """Loop principal de sincronizacion"""
        while self.running:
            try:
                await self.full_sync()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"MarkdownSyncService error: {e}")
                await asyncio.sleep(self.interval)

    # ================================================================
    # DB -> Markdown
    # ================================================================

    async def sync_lists_to_md(self) -> int:
        """
        Sincroniza PromptListModel entries a archivos MD.
        Returns number of files written.
        """
        lists = await self.prompt_store.list_all_lists()
        written = 0

        for pl in lists:
            slug = pl.get("slug")
            if not slug:
                continue

            filepath = os.path.join(self.lists_dir, f"{slug}.md")

            metadata = {
                "name": pl.get("name", ""),
                "slug": slug,
                "category": pl.get("category", "general"),
                "description": pl.get("description", ""),
                "is_active": pl.get("is_active", True),
            }

            # If file already exists, skip writing (MD -> DB takes priority;
            # only write when the file does not exist yet)
            if os.path.exists(filepath):
                continue

            content_md = pl.get("content_md", "")
            file_content = self._build_frontmatter(metadata) + "\n" + content_md

            self._write_file(filepath, file_content)
            written += 1
            log.debug(f"MD sync: wrote list '{slug}' -> {filepath}")

        return written

    async def sync_inbox_to_md(self) -> int:
        """
        Escribe prompts 'captured' del dia a data/prompt-inbox/YYYY/MM/YYYY-MM-DD.md.
        Returns number of prompts written.
        """
        captured = await self.prompt_store.get_captured_prompts(limit=200)
        if not captured:
            return 0

        now = utcnow_naive()
        today_str = now.strftime("%Y-%m-%d")

        # Filter to today's prompts only
        today_prompts = []
        for p in captured:
            created_at = p.get("created_at", "")
            if created_at and created_at.startswith(today_str):
                today_prompts.append(p)

        if not today_prompts:
            return 0

        year = now.strftime("%Y")
        month = now.strftime("%m")
        inbox_subdir = os.path.join(self.inbox_dir, year, month)
        os.makedirs(inbox_subdir, exist_ok=True)

        filepath = os.path.join(inbox_subdir, f"{today_str}.md")

        lines = [f"# Inbox {today_str}\n"]
        for p in today_prompts:
            created_at = p.get("created_at", "")
            time_str = "00:00"
            if created_at and "T" in created_at:
                time_part = created_at.split("T")[1]
                time_str = time_part[:5]

            content = p.get("content", "").replace("\n", " ").strip()
            tags = p.get("tags", [])
            priority = p.get("priority", 5)

            tag_str = " ".join(f"#{t}" for t in tags) if tags else ""
            entry = f"- [{time_str}] {content}"
            if tag_str:
                entry += f" {tag_str}"
            entry += f" (priority: {priority})"
            lines.append(entry)

        self._write_file(filepath, "\n".join(lines) + "\n")
        log.debug(f"MD sync: wrote {len(today_prompts)} inbox prompts -> {filepath}")
        return len(today_prompts)

    async def sync_archives_to_md(self) -> int:
        """
        Escribe prompts archivados a data/prompt-archives/YYYY/MM.md.
        Returns number of prompts written.
        """
        result = await self.prompt_store.get_archived_prompts(limit=500, offset=0)
        archived = result.get("prompts", [])
        if not archived:
            return 0

        # Group by year-month
        by_month: dict[str, list] = {}
        for p in archived:
            archived_at = p.get("archived_at") or p.get("created_at") or ""
            if archived_at:
                date_part = archived_at[:7]  # YYYY-MM
                by_month.setdefault(date_part, []).append(p)
            else:
                by_month.setdefault("unknown", []).append(p)

        total_written = 0
        for year_month, prompts in by_month.items():
            if year_month == "unknown":
                continue
            parts = year_month.split("-")
            if len(parts) != 2:
                continue
            year, month = parts

            archive_subdir = os.path.join(self.archive_dir, year)
            os.makedirs(archive_subdir, exist_ok=True)

            filepath = os.path.join(archive_subdir, f"{month}.md")

            lines = [f"# Archive {year}-{month}\n"]
            for p in prompts:
                content = p.get("content", "").replace("\n", " ").strip()
                category = p.get("category", "note")
                tags = p.get("tags", [])
                archived_at = p.get("archived_at") or p.get("created_at") or ""
                date_str = archived_at[:10] if archived_at else "?"

                tag_str = " ".join(f"#{t}" for t in tags) if tags else ""
                entry = f"- [{date_str}] [{category}] {content}"
                if tag_str:
                    entry += f" {tag_str}"
                lines.append(entry)

            self._write_file(filepath, "\n".join(lines) + "\n")
            total_written += len(prompts)
            log.debug(f"MD sync: wrote {len(prompts)} archived prompts -> {filepath}")

        return total_written

    # ================================================================
    # Markdown -> DB
    # ================================================================

    async def sync_md_to_lists(self) -> int:
        """
        Lee archivos MD de prompt-lists y actualiza DB.
        Returns number of lists upserted.
        """
        if not os.path.isdir(self.lists_dir):
            return 0

        upserted = 0
        for filename in os.listdir(self.lists_dir):
            if not filename.endswith(".md"):
                continue

            filepath = os.path.join(self.lists_dir, filename)
            try:
                raw = self._read_file(filepath)
            except Exception as e:
                log.warning(f"MD sync: could not read {filepath}: {e}")
                continue

            if not raw.strip():
                continue

            metadata, body = self._parse_frontmatter(raw)
            slug = metadata.get("slug") or filename.replace(".md", "")
            name = metadata.get("name") or slug.replace("-", " ").title()

            # Check if list exists in DB
            existing = await self.prompt_store.get_list(slug)

            if existing:
                # Update existing list with MD content
                update_fields = {
                    "content_md": body.strip(),
                }
                if metadata.get("name"):
                    update_fields["name"] = metadata["name"]
                if metadata.get("description"):
                    update_fields["description"] = metadata["description"]
                if metadata.get("category"):
                    update_fields["category"] = metadata["category"]
                if "is_active" in metadata:
                    update_fields["is_active"] = self._parse_bool(metadata["is_active"])

                await self.prompt_store.update_list(slug, **update_fields)
                log.debug(f"MD sync: updated list '{slug}' from {filepath}")
            else:
                # Create new list from MD file
                await self.prompt_store.create_list(
                    name=name,
                    description=metadata.get("description", ""),
                    category=metadata.get("category", "general"),
                    content_md=body.strip(),
                )
                log.debug(f"MD sync: created list '{slug}' from {filepath}")

            upserted += 1

        return upserted

    # ================================================================
    # Full Sync
    # ================================================================

    async def full_sync(self) -> dict:
        """
        Ejecuta sync completo en ambas direcciones.
        MD -> DB first (human edits take priority).
        Then DB -> MD (reflect any DB-only changes).
        """
        result = {
            "md_to_db_lists": 0,
            "db_to_md_lists": 0,
            "inbox_prompts": 0,
            "archive_prompts": 0,
            "errors": [],
        }

        # MD -> DB first (human edits take priority)
        try:
            result["md_to_db_lists"] = await self.sync_md_to_lists()
        except Exception as e:
            log.error(f"MD sync error (md_to_lists): {e}")
            result["errors"].append(f"md_to_lists: {str(e)}")

        # DB -> MD (reflect DB-only changes)
        try:
            result["db_to_md_lists"] = await self.sync_lists_to_md()
        except Exception as e:
            log.error(f"MD sync error (lists_to_md): {e}")
            result["errors"].append(f"lists_to_md: {str(e)}")

        try:
            result["inbox_prompts"] = await self.sync_inbox_to_md()
        except Exception as e:
            log.error(f"MD sync error (inbox_to_md): {e}")
            result["errors"].append(f"inbox_to_md: {str(e)}")

        try:
            result["archive_prompts"] = await self.sync_archives_to_md()
        except Exception as e:
            log.error(f"MD sync error (archives_to_md): {e}")
            result["errors"].append(f"archives_to_md: {str(e)}")

        self.last_sync = utcnow_naive()
        self.last_sync_result = result
        self.sync_count += 1

        log.debug(
            f"MarkdownSync: full_sync #{self.sync_count} "
            f"(md->db:{result['md_to_db_lists']}, db->md:{result['db_to_md_lists']}, "
            f"inbox:{result['inbox_prompts']}, archive:{result['archive_prompts']})"
        )

        return result

    # ================================================================
    # Helpers
    # ================================================================

    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """
        Parsea frontmatter YAML (entre --- markers) y devuelve (metadata, body).
        No requiere pyyaml - parseo manual de key: value lines.
        """
        metadata: dict = {}
        body = content

        stripped = content.strip()
        if not stripped.startswith("---"):
            return metadata, content

        # Find second --- marker
        first_marker = stripped.index("---")
        rest = stripped[first_marker + 3:]
        second_marker_pos = rest.find("\n---")

        if second_marker_pos == -1:
            return metadata, content

        frontmatter_block = rest[:second_marker_pos].strip()
        body = rest[second_marker_pos + 4:]  # skip \n---

        # Parse key: value lines
        for line in frontmatter_block.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            colon_pos = line.find(":")
            if colon_pos == -1:
                continue

            key = line[:colon_pos].strip()
            value = line[colon_pos + 1:].strip()

            # Handle boolean-like values
            if value.lower() in ("true", "yes"):
                metadata[key] = True
            elif value.lower() in ("false", "no"):
                metadata[key] = False
            # Handle list values [item1, item2]
            elif value.startswith("[") and value.endswith("]"):
                items = value[1:-1]
                metadata[key] = [
                    item.strip().strip("'\"")
                    for item in items.split(",")
                    if item.strip()
                ]
            else:
                # Strip surrounding quotes
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                metadata[key] = value

        return metadata, body

    def _build_frontmatter(self, metadata: dict) -> str:
        """Construye bloque frontmatter YAML"""
        lines = ["---"]
        for key, value in metadata.items():
            if isinstance(value, bool):
                lines.append(f"{key}: {'true' if value else 'false'}")
            elif isinstance(value, list):
                items = ", ".join(str(v) for v in value)
                lines.append(f"{key}: [{items}]")
            elif value is None:
                lines.append(f"{key}: ")
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        return "\n".join(lines)

    def _ensure_dirs(self):
        """Crea directorios necesarios si no existen"""
        os.makedirs(self.lists_dir, exist_ok=True)
        os.makedirs(self.inbox_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)

    def _read_file(self, filepath: str) -> str:
        """Lee un archivo de texto"""
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def _write_file(self, filepath: str, content: str):
        """Escribe un archivo de texto, creando directorios intermedios"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    def _parse_bool(self, value) -> bool:
        """Parsea valor a bool"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1")
        return bool(value)

    def get_status(self) -> dict:
        """Returns current sync status for API consumption"""
        return {
            "running": self.running,
            "interval_seconds": self.interval,
            "sync_count": self.sync_count,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "last_sync_result": self.last_sync_result,
            "directories": {
                "lists": self.lists_dir,
                "inbox": self.inbox_dir,
                "archives": self.archive_dir,
            },
        }

    async def get_today_inbox_md(self) -> str:
        """Returns today's inbox markdown content (or empty string)"""
        now = utcnow_naive()
        today_str = now.strftime("%Y-%m-%d")
        year = now.strftime("%Y")
        month = now.strftime("%m")

        filepath = os.path.join(self.inbox_dir, year, month, f"{today_str}.md")
        if os.path.exists(filepath):
            return self._read_file(filepath)
        return ""
