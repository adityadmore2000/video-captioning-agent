"""Best-effort ``.env`` loading for local and container runs.

Loaded once at startup (pipeline ``main`` and the demo app) so env-driven
config — ``FIREWORKS_API_KEY`` and the ``FIREWORKS_VISION_*`` provisioning
variables — is available without an explicit ``--env-file`` Docker flag or a
separate ``-e`` for every variable.

Precedence (matches ``override=False`` in python-dotenv):

1. Values already in the environment (shell ``export``, Docker ``-e``,
   ``--env-file``) always win and are never clobbered by the ``.env`` file.
2. The ``.env`` file fills in anything not already set.
3. Code-level defaults/``None`` apply when neither source provides a value.

Default discovery resolves ``.env`` relative to the current working
directory (not python-dotenv's file-tree walk, which is unpredictable across
install layouts). In Docker the image ``WORKDIR`` is ``/app``, so mounting
``.env`` to ``/app/.env`` makes it found automatically. Set ``DOTENV_PATH``
to point at a different file. A missing ``.env`` or an unavailable
``python-dotenv`` install is a silent no-op: env vars supplied through the
shell or ``-e`` still work.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file() -> None:
    """Populate ``os.environ`` from a ``.env`` file, best-effort.

    Never raises: a missing file, an unset ``DOTENV_PATH`` target, or an
    unavailable ``python-dotenv`` install all degrade to a no-op, leaving
    the existing environment untouched.
    """

    dotenv_path = Path(os.environ.get("DOTENV_PATH") or (Path.cwd() / ".env"))
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(dotenv_path, override=False)
