"""Device discovery message handler.

Parses incoming IoT messages, extracts (chip_id, node) tuples,
and persists them to the database via a background worker thread.
Also detects special event types and queues them for storage.
"""

import logging
import queue
import threading
from typing import TYPE_CHECKING

from message_listener.abstract.handler_interface import Handler

if TYPE_CHECKING:  # noqa: F401
    from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# Supported event types that trigger event data storage.
SUPPORTED_EVENTS = frozenset({
    "system.pong",
    "system.microplate.hash",
    "system.userspace.hash",
})

# Queue item types:
#   ("device", chip_id, node)
#   ("event", chip_id, node, event_type, parameters)
QueueItem = tuple[str, str, str] | tuple[str, str, str, str, dict]


class MessageHandler(Handler):
    """Parse incoming IoT messages and queue device discovery tuples."""

    def __init__(self) -> None:
        self.queue: queue.Queue[QueueItem] = queue.Queue()
        self.cache: set[tuple[str, str]] = set()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None

    # -- public API ----------------------------------------------------------

    def handle(self, message) -> None:
        """Parse a single message and push (chip_id, node) onto the queue."""
        if message is None or message.data is None:
            logger.debug("Skipping None message or message with no data")
            return

        data = message.data
        raw_chip_id = data.get("chip_id") if isinstance(data, dict) else None
        node = data.get("node") if isinstance(data, dict) else None

        # Normalize chip_id to string (some devices send int chip_ids).
        chip_id = str(raw_chip_id).strip() if raw_chip_id is not None else ""

        # Treat empty strings as missing.
        if not chip_id:
            logger.warning("Skipping message — missing or empty chip_id: %s", data)
            return
        if not node or not isinstance(node, str) or not node.strip():
            logger.warning("Skipping message — missing or empty node: %s", data)
            return

        # Always queue device discovery tuple.
        self.queue.put_nowait(("device", chip_id, node))
        logger.info("Queued device discovery: (%s, %s)", chip_id, node)

        # Check for supported event type.
        event_type = data.get("event") if isinstance(data, dict) else None
        if event_type in SUPPORTED_EVENTS:
            parameters = data.get("parameters", {})
            self.queue.put_nowait((
                "event", chip_id, node, event_type, parameters
            ))
            logger.info(
                "Queued event %s for (%s, %s)", event_type, chip_id, node
            )

    def start(self) -> None:
        """Launch the background discovery worker thread."""
        if self._worker is not None and self._worker.is_alive():
            logger.warning("Worker already running")
            return
        self._stop_event.clear()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        logger.info("Discovery worker started")

    def stop(self) -> None:
        """Signal the worker to halt and wait for it to finish."""
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=5.0)
        logger.info("Discovery worker stopped")

    # -- internal -------------------------------------------------------------

    def _worker_loop(self) -> None:
        """Drain the queue and persist devices/events to the database."""
        from app.db.session import SessionLocal

        while not self._stop_event.is_set():
            try:
                item = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue

            tag = item[0]
            if tag == "device":
                _, chip_id, node = item
                self._process(chip_id, node, SessionLocal)
            elif tag == "event":
                _, chip_id, node, event_type, parameters = item
                self._process_event(
                    chip_id, node, event_type, parameters, SessionLocal
                )
            else:
                logger.warning("Unknown queue item tag: %s", tag)

    def _process(
        self, chip_id: str, node: str, session_factory: "SessionLocal",
    ) -> None:
        """Deduplicate and persist a single (chip_id, node) pair."""
        from app.crud.device import create_device, get_device_by_pair
        from app.schemas.device import DeviceCreate
        from sqlalchemy.exc import IntegrityError

        pair = (chip_id, node)

        # Fast-path: in-memory cache.
        if pair in self.cache:
            return

        db = session_factory()
        try:
            existing = get_device_by_pair(db, chip_id, node)
            if existing is not None:
                self.cache.add(pair)
                return

            db_obj = create_device(
                db, DeviceCreate(chip_id=chip_id, node=node)
            )
            self.cache.add(pair)
            logger.info("New device created: %s (id=%s)", node, db_obj.id)
        except IntegrityError:
            db.rollback()
            logger.warning(
                "IntegrityError inserting device (%s, %s) — "
                "likely concurrent insert",
                chip_id,
                node,
            )
            self.cache.add(pair)
        finally:
            db.close()

    def _process_event(
        self,
        chip_id: str,
        node: str,
        event_type: str,
        parameters: dict,
        session_factory: "SessionLocal",
    ) -> None:
        """Get or create device, then upsert event data."""
        from app.crud.device_event import get_or_create_device, upsert_event
        from sqlalchemy.exc import IntegrityError

        db = session_factory()
        try:
            device = get_or_create_device(db, chip_id, node)
            upsert_event(db, device.id, event_type, parameters)
            logger.info(
                "Upserted event %s for device %s", event_type, device.id
            )
        except IntegrityError:
            db.rollback()
            logger.warning(
                "IntegrityError upserting event %s for (%s, %s)",
                event_type, chip_id, node,
            )
        except Exception:
            db.rollback()
            logger.exception(
                "Error processing event %s for (%s, %s)",
                event_type, chip_id, node,
            )
        finally:
            db.close()
