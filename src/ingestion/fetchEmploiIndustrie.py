"""
Scraper async pour lindustrie-recrute.fr
-----------------------------------------
Usage rapide :
    python lindustrie_scraper.py                        # plage auto (max_id déduit)
    python lindustrie_scraper.py --start 810000 --end 818356
    python lindustrie_scraper.py --resume               # reprend depuis checkpoint
    python lindustrie_scraper.py --to-parquet           # convertit le JSONL → Parquet
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

# ─── Configuration ────────────────────────────────────────────────────────────

BASE_URL = "https://www.lindustrie-recrute.fr/candidat/offre/{id}"
OUTPUT_JSONL = Path("lindustrie_offres.jsonl")
CHECKPOINT_FILE = Path("lindustrie_checkpoint.txt")
LOG_FILE = Path("lindustrie_scraper.log")

# Plage d'IDs à scraper (bornes incluses)
DEFAULT_ID_START = 300_000          # à ajuster selon exploration préalable
DEFAULT_ID_END   = 818_356

CONCURRENCY      = 8                # workers async simultanés
REQUEST_TIMEOUT  = 15               # secondes
RETRY_MAX        = 3                # tentatives par ID
RETRY_BASE_DELAY = 1.5              # secondes (backoff exponentiel)
RATE_SLEEP_MIN   = 0.05             # délai min entre requêtes (par worker)
RATE_SLEEP_MAX   = 0.25             # délai max entre requêtes (par worker)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ─── Modèle de données ────────────────────────────────────────────────────────

@dataclass
class LindustrieOffer:
    """
    Représentation normalisée d'une offre lindustrie-recrute.fr.
    Champs alignés sur FranceTravailOfferParser pour compatibilité pipeline.
    """
    id: str
    source: str = "lindustrie_recrute"

    # Intitulé / description
    titre: Optional[str] = None
    description: Optional[str] = None

    # Contrat
    type_contrat: Optional[str] = None
    type_contrat_libelle: Optional[str] = None
    nature_contrat: Optional[str] = None

    # Expérience / qualification
    experience_exige: Optional[str] = None
    experience_libelle: Optional[str] = None
    qualification_libelle: Optional[str] = None

    # Localisation
    code_departement: Optional[str] = None
    lieu_travail_libelle: Optional[str] = None
    region: Optional[str] = None

    # Entreprise / secteur
    nom_acheteur: Optional[str] = None
    secteur: Optional[str] = None
    code_naf: Optional[str] = None
    code_rome: Optional[str] = None
    rome_libelle: Optional[str] = None
    appellation_libelle: Optional[str] = None

    # Postes / flags
    nombre_postes: Optional[int] = None
    alternance: bool = False
    accessible_th: bool = False

    # Dates
    date_publication: Optional[str] = None
    date_creation: Optional[str] = None
    date_modification: Optional[str] = None

    # Référence interne du site
    reference_interne: Optional[str] = None

    # Données brutes
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Parser HTML ──────────────────────────────────────────────────────────────

class LindustrieOfferParser:
    """
    Parse le HTML d'une page offre lindustrie-recrute.fr
    et retourne un LindustrieOffer normalisé.
    """

    # Mappings contractuels courants présents sur le site
    _CONTRAT_NORM: Dict[str, str] = {
        "cdi": "CDI",
        "cdd": "CDD",
        "alternance": "ALT",
        "stage": "STG",
        "interim": "MIS",
        "freelance": "LIB",
        "apprentissage": "ALT",
    }

    def __init__(self, offer_id: int, html: str):
        self.offer_id = offer_id
        self.soup = BeautifulSoup(html, "lxml")
        self._raw: Dict[str, Any] = {}

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _clean(text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        return re.sub(r"\s+", " ", text).strip() or None

    def _text(self, selector: str, attr: Optional[str] = None) -> Optional[str]:
        el = self.soup.select_one(selector)
        if el is None:
            return None
        val = el.get(attr) if attr else el.get_text()
        return self._clean(val)

    def _meta(self, name: str) -> Optional[str]:
        el = self.soup.find("meta", attrs={"name": name}) or \
             self.soup.find("meta", attrs={"property": name})
        return self._clean(el.get("content")) if el else None

    # ── champs individuels ────────────────────────────────────────────────────

    def _parse_titre(self) -> Optional[str]:
        # Priorité : balise <h1>, puis og:title, puis <title>
        return (
            self._text("h1.job-title")
            or self._text("h1")
            or self._meta("og:title")
            or self._text("title")
        )

    def _parse_description(self) -> Optional[str]:
        for sel in [
            ".job-description",
            ".offer-description",
            ".description-offre",
            "div[class*='description']",
            "section[class*='description']",
        ]:
            txt = self._text(sel)
            if txt:
                return txt
        return None

    def _parse_entreprise(self) -> Optional[str]:
        for sel in [".company-name", ".entreprise", "[class*='company']", "[class*='entreprise']"]:
            txt = self._text(sel)
            if txt:
                return txt
        return None

    def _parse_lieu(self) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Retourne (code_dept, libelle_lieu, region)."""
        raw_lieu = None
        for sel in [".location", ".lieu", "[class*='location']", "[class*='lieu']"]:
            raw_lieu = self._text(sel)
            if raw_lieu:
                break

        code_dept, region = None, None
        if raw_lieu:
            # Format courant : "Île-de-France (75)"  ou "75 - Paris"
            m = re.search(r"\((\d{2,3})\)", raw_lieu)
            if m:
                code_dept = m.group(1)
            else:
                m = re.search(r"^(\d{2,3})\s*[-–]", raw_lieu)
                if m:
                    code_dept = m.group(1)
        return code_dept, raw_lieu, region

    def _parse_contrat(self) -> tuple[Optional[str], Optional[str]]:
        raw = None
        for sel in [".contract-type", ".type-contrat", "[class*='contrat']", "[class*='contract']"]:
            raw = self._text(sel)
            if raw:
                break
        if not raw:
            return None, None
        libelle = self._clean(raw)
        code = self._CONTRAT_NORM.get(libelle.lower() if libelle else "", None)
        return code, libelle

    def _parse_experience(self) -> tuple[Optional[str], Optional[str]]:
        for sel in [".experience", "[class*='experience']"]:
            txt = self._text(sel)
            if txt:
                return None, txt
        return None, None

    def _parse_date(self) -> Optional[str]:
        # Cherche meta date ou texte lisible
        for sel in ["time[datetime]"]:
            dt = self._text(sel, attr="datetime")
            if dt:
                return dt[:10]   # ISO date
        raw = self._meta("article:published_time") or self._meta("datePublished")
        if raw:
            return raw[:10]
        return None

    def _parse_reference(self) -> Optional[str]:
        for sel in [".reference", ".ref", "[class*='reference']", "[class*='ref-offre']"]:
            txt = self._text(sel)
            if txt:
                m = re.search(r"[A-Z0-9]{6,}", txt)
                if m:
                    return m.group(0)
        return None

    def _parse_alternance(self) -> bool:
        contrat_txt = self.soup.get_text().lower()
        return "alternance" in contrat_txt or "apprentissage" in contrat_txt

    def _parse_nombre_postes(self) -> Optional[int]:
        for sel in ["[class*='postes']", "[class*='poste']"]:
            txt = self._text(sel)
            if txt:
                m = re.search(r"\d+", txt)
                if m:
                    return int(m.group(0))
        return None

    def _parse_secteur(self) -> Optional[str]:
        for sel in ["[class*='secteur']", "[class*='sector']", "[class*='activite']"]:
            txt = self._text(sel)
            if txt:
                return txt
        return None

    # ── parsing JSON-LD structuré (si présent) ────────────────────────────────

    def _parse_json_ld(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        for tag in self.soup.find_all("script", type="application/ld+json"):
            try:
                blob = json.loads(tag.string or "")
                if isinstance(blob, list):
                    blob = blob[0]
                if blob.get("@type") in ("JobPosting", "jobPosting"):
                    data = blob
                    break
            except (json.JSONDecodeError, AttributeError):
                continue
        return data

    # ── entrée principale ─────────────────────────────────────────────────────

    def parse(self) -> LindustrieOffer:
        ld = self._parse_json_ld()
        self._raw = ld  # conservé comme raw_data de référence

        code_dept, lieu_libelle, region = self._parse_lieu()
        type_contrat_code, type_contrat_libelle = self._parse_contrat()
        exp_exige, exp_libelle = self._parse_experience()
        date_pub = self._parse_date()

        # JSON-LD enrichit les champs si disponibles
        titre = (
            self._clean(ld.get("title"))
            or self._clean(ld.get("name"))
            or self._parse_titre()
        )
        description = (
            self._clean(ld.get("description"))
            or self._parse_description()
        )
        nom_acheteur = (
            self._clean(ld.get("hiringOrganization", {}).get("name"))
            or self._parse_entreprise()
        )
        if not lieu_libelle and ld.get("jobLocation"):
            loc = ld["jobLocation"]
            if isinstance(loc, dict):
                addr = loc.get("address", {})
                lieu_libelle = self._clean(
                    addr.get("addressLocality") or addr.get("addressRegion")
                )
                code_dept = self._clean(addr.get("postalCode", "")[:2]) or code_dept
        if not type_contrat_libelle and ld.get("employmentType"):
            type_contrat_libelle = self._clean(ld["employmentType"])
        if not date_pub and ld.get("datePosted"):
            date_pub = ld["datePosted"][:10]

        alternance = (
            "alternance" in (type_contrat_libelle or "").lower()
            or self._parse_alternance()
        )

        return LindustrieOffer(
            id=str(self.offer_id),
            titre=titre,
            description=description,
            type_contrat=type_contrat_code,
            type_contrat_libelle=type_contrat_libelle,
            experience_exige=exp_exige,
            experience_libelle=exp_libelle,
            code_departement=code_dept,
            lieu_travail_libelle=lieu_libelle,
            region=region,
            nom_acheteur=nom_acheteur,
            secteur=self._parse_secteur(),
            nombre_postes=self._parse_nombre_postes(),
            alternance=alternance,
            date_publication=date_pub,
            date_creation=date_pub,
            date_modification=date_pub,
            reference_interne=self._parse_reference(),
            raw_data=self._raw,
        )


# ─── Scraper principal ────────────────────────────────────────────────────────

class LindustrieScraper:
    """
    Scraper async pour lindustrie-recrute.fr.

    Fonctionnement :
    - Génère une queue d'IDs à traiter
    - N workers async consomment la queue en parallèle
    - Chaque offre valide est appendée au fichier JSONL de sortie
    - Le dernier ID traité est écrit dans un checkpoint pour reprise
    """

    def __init__(
        self,
        id_start: int = DEFAULT_ID_START,
        id_end: int = DEFAULT_ID_END,
        output_path: Path = OUTPUT_JSONL,
        checkpoint_path: Path = CHECKPOINT_FILE,
        concurrency: int = CONCURRENCY,
        resume: bool = False,
    ):
        self.id_start = id_start
        self.id_end = id_end
        self.output_path = output_path
        self.checkpoint_path = checkpoint_path
        self.concurrency = concurrency
        self.resume = resume

        self._semaphore: asyncio.Semaphore
        self._queue: asyncio.Queue
        self._lock = asyncio.Lock()

        self.stats = {
            "fetched": 0,
            "parsed": 0,
            "not_found": 0,
            "errors": 0,
            "skipped": 0,
        }

    # ── checkpoint ────────────────────────────────────────────────────────────

    def _load_checkpoint(self) -> int:
        if self.resume and self.checkpoint_path.exists():
            try:
                last = int(self.checkpoint_path.read_text().strip())
                log.info(f"Reprise depuis l'ID {last + 1}")
                return last + 1
            except ValueError:
                pass
        return self.id_start

    def _save_checkpoint(self, offer_id: int) -> None:
        self.checkpoint_path.write_text(str(offer_id))

    # ── écriture ──────────────────────────────────────────────────────────────

    async def _write_offer(self, offer: LindustrieOffer) -> None:
        async with self._lock:
            with self.output_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(offer.to_dict(), ensure_ascii=False, default=str) + "\n")

    # ── HTTP ──────────────────────────────────────────────────────────────────

    async def _fetch(self, client: httpx.AsyncClient, offer_id: int) -> Optional[str]:
        url = BASE_URL.format(id=offer_id)
        for attempt in range(1, RETRY_MAX + 1):
            try:
                await asyncio.sleep(random.uniform(RATE_SLEEP_MIN, RATE_SLEEP_MAX))
                resp = await client.get(url, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    return resp.text
                if resp.status_code in (404, 410):
                    return None          # offre inexistante, normal
                if resp.status_code == 429:
                    wait = 10 * attempt
                    log.warning(f"[{offer_id}] 429 rate-limit – attente {wait}s")
                    await asyncio.sleep(wait)
                    continue
                log.warning(f"[{offer_id}] HTTP {resp.status_code} (attempt {attempt})")
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                log.warning(f"[{offer_id}] {type(e).__name__} (attempt {attempt}): {e}")
            if attempt < RETRY_MAX:
                await asyncio.sleep(RETRY_BASE_DELAY ** attempt)
        return None

    # ── worker ────────────────────────────────────────────────────────────────

    async def _worker(self, client: httpx.AsyncClient) -> None:
        while True:
            try:
                offer_id: int = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            async with self._semaphore:
                html = await self._fetch(client, offer_id)

            if html is None:
                self.stats["not_found"] += 1
                self._queue.task_done()
                continue

            self.stats["fetched"] += 1

            try:
                offer = LindustrieOfferParser(offer_id, html).parse()
                if offer.titre:
                    await self._write_offer(offer)
                    self.stats["parsed"] += 1
                    self._save_checkpoint(offer_id)
                else:
                    # Page existe mais vide / redirigée
                    self.stats["not_found"] += 1
            except Exception as e:
                log.error(f"[{offer_id}] Parsing error: {e}", exc_info=True)
                self.stats["errors"] += 1

            self._queue.task_done()

            # Log de progression
            total_done = sum(self.stats.values())
            if total_done % 500 == 0:
                log.info(f"Progression : {self.stats}")

    # ── entrée principale ─────────────────────────────────────────────────────

    async def run(self) -> None:
        start_id = self._load_checkpoint()
        total = self.id_end - start_id + 1
        log.info(f"Scraping de {start_id} à {self.id_end} ({total} IDs)")

        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._queue = asyncio.Queue()

        for offer_id in range(start_id, self.id_end + 1):
            await self._queue.put(offer_id)

        t0 = time.monotonic()
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
            workers = [
                asyncio.create_task(self._worker(client))
                for _ in range(self.concurrency)
            ]
            await asyncio.gather(*workers)

        elapsed = time.monotonic() - t0
        log.info(
            f"Terminé en {elapsed:.1f}s | "
            f"parsés={self.stats['parsed']} | "
            f"not_found={self.stats['not_found']} | "
            f"erreurs={self.stats['errors']}"
        )

    def run_sync(self) -> None:
        asyncio.run(self.run())


# ─── Conversion JSONL → Parquet ───────────────────────────────────────────────

def convert_to_parquet(jsonl_path: Path = OUTPUT_JSONL) -> None:
    """Convertit le JSONL en Parquet via DuckDB (zéro dépendance pandas)."""
    import duckdb
    out = jsonl_path.with_suffix(".parquet")
    con = duckdb.connect()
    con.execute(f"""
        COPY (
            SELECT * FROM read_json_auto('{jsonl_path}', ignore_errors=true)
        )
        TO '{out}' (FORMAT PARQUET, COMPRESSION 'zstd')
    """)
    log.info(f"Parquet écrit : {out}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Scraper lindustrie-recrute.fr")
    parser.add_argument("--start", type=int, default=DEFAULT_ID_START)
    parser.add_argument("--end",   type=int, default=DEFAULT_ID_END)
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY)
    parser.add_argument("--output", type=Path, default=OUTPUT_JSONL)
    parser.add_argument("--resume", action="store_true",
                        help="Reprend depuis le dernier checkpoint")
    parser.add_argument("--to-parquet", action="store_true",
                        help="Convertit le JSONL existant en Parquet puis quitte")
    args = parser.parse_args()

    if args.to_parquet:
        convert_to_parquet(args.output)
        return

    scraper = LindustrieScraper(
        id_start=args.start,
        id_end=args.end,
        output_path=args.output,
        concurrency=args.concurrency,
        resume=args.resume,
    )
    scraper.run_sync()


if __name__ == "__main__":
    main()