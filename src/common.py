"""Shared helpers: config loading, paths, logging."""

import logging
import sys
from pathlib import Path

import yaml

# Windows consoles default to cp1252, which chokes on emoji in titles/transcripts
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"
DOCS_DIR = ROOT / "docs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_settings() -> dict:
    return load_yaml("settings.yaml")


def ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    return OUTPUT_DIR
