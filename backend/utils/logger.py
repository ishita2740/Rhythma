"""Project-wide logger.

Kept as the single import path for logging (``from utils.logger import
logger``) so no call site has to know how logging is configured. The actual
sinks, level, JSON formatting and PII redaction live in
:mod:`core.logging_config`, which ``main.py`` configures once at startup.

Importing this module does *not* configure logging — that would create an
import cycle, since ``core.errors`` imports both this module and
``core.logging_config``. Until ``configure_logging()`` runs, loguru's
default stderr sink applies, which is the right behaviour for the scripts
under ``backend/scripts/`` that import services without booting the app.
"""

from loguru import logger

__all__ = ["logger"]
