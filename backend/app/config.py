"""Yerel ayarlar: proje kökündeki .env dosyası ve ortam değişkenleri."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_env(path=PROJECT_ROOT / ".env"):
    """Basit KEY=VALUE satırlarını oku. Terminalde tanımlı değişken önceliklidir."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def running_on_vercel():
    """Vercel her fonksiyonda VERCEL=1 tanımlar; yerelde tanımlı değildir."""
    return bool(os.environ.get("VERCEL"))
