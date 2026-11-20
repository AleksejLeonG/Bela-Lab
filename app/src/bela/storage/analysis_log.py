"""Durable advice diagnostics, separate from game archives and hidden worlds."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

from bela.paths import SAVES_ROOT
from bela.storage.user_storage import dumps_user_match


def analysis_record(match, advice, **context):
    """Freeze original input and every estimate; never serialize sampled hands."""
    return {"format": "bela-analysis-record", "schema_version": 1,
            "record_id": str(uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
            "provenance": "original_analysis", "context": context,
            "input": json.loads(dumps_user_match(match)), "advice": advice}


def append_analysis(path, record):
    """Flush before gameplay advances. Each writer owns its journal file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, allow_nan=False) + "\n"
    with target.open("a", encoding="utf-8") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return target


def save_analysis(match, advice, *, directory=None, **context):
    record = analysis_record(match, advice, **context)
    directory = Path(directory) if directory is not None else SAVES_ROOT / "analysis"
    return append_analysis(directory / (record["record_id"] + ".jsonl"), record)
