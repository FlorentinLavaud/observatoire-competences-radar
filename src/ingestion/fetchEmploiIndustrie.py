"""
Scraper async pour lindustrie-recrute.fr
-----------------------------------------
Usage :
    python lindustrie_scraper.py --start 700000 --end 818356
    python lindustrie_scraper.py --resume
    python lindustrie_scraper.py --to-parquet
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
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Union

import httpx
from bs4 import BeautifulSoup, Tag

# ─── Configuration ────────────────────────────────────────────────────────────

BASE_URL         = "https://www.lindustrie-recrute.fr/candidat/offre/{id}"
OUTPUT_JSONL     = Path("lindustrie_offres.jsonl")
CHECKPOINT_FILE  = Path("lindustrie_checkpoint.txt")
LOG_FILE         = Path("lindustrie_scraper.log")

DEFAULT_ID_START = 700_000
DEFAULT_ID_END   = 818_356

CONCURRENCY      = 8
REQUEST_TIMEOUT  = 20
RETRY_MAX        = 3
RETRY_BASE_DELAY = 1.5
RATE_SLEEP_MIN   = 0.05
RATE_SLEEP_MAX   = 0.25
WAF_COOKIE_TTL   = 3_600   # secondes avant renouvellement préventif

BASE_HEADERS = {
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
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# Type de retour du parser
ParseResult = Union["LindustrieOffer", Literal["404", "waf"]]


# ─── Modèle de données ────────────────────────────────────────────────────────

@dataclass
class LindustrieOffer:
    """Schéma normalisé aligné sur FranceTravailOfferParser."""
    id: str
    source: str = "lindustrie_recrute"
    titre: Optional[str] = None
    description: Optional[str] = None
    type_contrat: Optional[str] = None
    type_contrat_libelle: Optional[str] = None
    nature_contrat: Optional[str] = None
    experience_exige: Optional[str] = None
    experience_libelle: Optional[str] = None
    qualification_libelle: Optional[str] = None   # niveau d'études
    code_departement: Optional[str] = None
    lieu_travail_libelle: Optional[str] = None    # "Cruas (07350)"
    region: Optional[str] = None
    nom_acheteur: Optional[str] = None
    secteur: Optional[str] = None
    code_naf: Optional[str] = None
    code_rome: Optional[str] = None
    rome_libelle: Optional[str] = None
    appellation_libelle: Optional[str] = None
    nombre_postes: Optional[int] = None
    alternance: bool = False
    accessible_th: bool = False
    salaire_libelle: Optional[str] = None
    date_publication: Optional[str] = None
    date_creation: Optional[str] = None
    date_modification: Optional[str] = None
    reference_interne: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Parser HTML ──────────────────────────────────────────────────────────────

class LindustrieOfferParser:
    """
    Parse le HTML d'une page offre lindustrie-recrute.fr.

    Stratégie en 2 couches :
      1. JSON-LD JobPosting (présent sur toutes les pages offre valides)
      2. Sélecteurs CSS ciblés sur les classes réelles du template UIMM
    """

    _CONTRAT_NORM: Dict[str, str] = {
        "cdi": "CDI", "cdd": "CDD", "alternance": "ALT",
        "stage": "STG", "interim": "MIS", "intérim": "MIS",
        "freelance": "LIB", "apprentissage": "ALT",
        "temps complet": None, "temps partiel": None,  # nature, pas type
    }

    def __init__(self, offer_id: int, html: str):
        self.offer_id = offer_id
        self.soup = BeautifulSoup(html, "lxml")

    # ── détection du type de page ─────────────────────────────────────────────

    def page_type(self) -> Literal["offer", "404", "waf"]:
        body = self.soup.find("body")
        if not body or not isinstance(body, Tag):
            return "waf"
        classes = body.get("class", [])
        # Offre valide : body class="paged-XXXXXXX"
        if any(c.startswith("paged-") for c in classes):
            return "offer"
        # 404 : body class="error404"
        if "error404" in classes:
            return "404"
        # WAF : pas de body reconnaissable ou script AWS WAF
        if self.soup.find("script", src=re.compile(r"awswaf")):
            return "waf"
        return "waf"   # fallback conservateur

    # ── helpers ───────────────────────────────────────────────────────────────

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
        return self._clean(str(val) if val else None)

    def _meta(self, prop: str) -> Optional[str]:
        el = (self.soup.find("meta", attrs={"name": prop})
              or self.soup.find("meta", attrs={"property": prop}))
        return self._clean(el.get("content")) if el else None  # type: ignore

    # ── JSON-LD ───────────────────────────────────────────────────────────────

    def _parse_json_ld(self) -> Dict[str, Any]:
        """Récupère le bloc JobPosting du JSON-LD embarqué."""
        for tag in self.soup.find_all("script", type="application/ld+json"):
            try:
                blob = json.loads(tag.string or "")
                if isinstance(blob, list):
                    blob = blob[0]
                if blob.get("@type") in ("JobPosting", "jobPosting"):
                    return blob
            except (json.JSONDecodeError, AttributeError):
                continue
        return {}

    # ── extraction ciblée (fallback / complément du JSON-LD) ─────────────────

    def _parse_lieu(self) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extrait (code_dept, libelle_lieu, region) depuis .offer-details__where
        ou le JSON-LD jobLocation.
        Format observé : "Cruas (07350)"
        """
        raw = self._text(".offer-details__where")
        if raw:
            # Retire le nom d'entreprise qui précède " - "
            if " - " in raw:
                raw = raw.split(" - ", 1)[1]
            raw = self._clean(raw)

        region = None
        code_dept = None
        if raw:
            m = re.search(r"\((\d{2,3})\d{3}\)", raw)  # "(07350)" → "07"
            if m:
                code_dept = m.group(1)
            else:
                m = re.search(r"\((\d{2,3})\)", raw)   # "(07)" → "07"
                if m:
                    code_dept = m.group(1)
        return code_dept, raw, region

    def _parse_offer_datas(self) -> Dict[str, Optional[str]]:
        """
        Extrait les métadonnées de la sidebar (.offer-datas).
        Chaque bloc contient une icône uimm-icon et un texte.
        Icônes observées : pin, experience, etudes, contrat, time
        """
        result: Dict[str, Optional[str]] = {
            "contrat": None, "experience": None,
            "etudes": None, "temps": None,
        }
        for bloc in self.soup.select(".offer-datas"):
            icon_el = bloc.select_one(".uimm-icon")
            text_el = bloc.find("div")
            if not icon_el or not text_el:
                continue
            icon_classes = icon_el.get("class", [])
            txt = self._clean(text_el.get_text())
            if "contrat" in icon_classes:
                result["contrat"] = txt
            elif "experience" in icon_classes:
                result["experience"] = txt
            elif "etudes" in icon_classes:
                result["etudes"] = txt
            elif "time" in icon_classes:
                result["temps"] = txt
        return result

    def _parse_reference(self) -> Optional[str]:
        txt = self._text(".offer-details__metas .ref")
        if txt:
            m = re.search(r"Ref\s*:\s*(.+)", txt, re.IGNORECASE)
            if m:
                return self._clean(m.group(1))
        return None

    def _parse_salaire(self) -> Optional[str]:
        """
        Le salaire n'est pas dans le JSON-LD ; il apparaît dans les cards
        de résultats similaires (.offer-card__datas-item avec .salaire).
        Sur la page de détail, chercher dans le texte libre.
        """
        for el in self.soup.select(".offer-card__datas-item"):
            icon = el.select_one(".uimm-icon.salaire")
            if icon:
                txt = self._clean(el.get_text())
                if txt and txt.lower() != "selon profil":
                    return txt
        return None

    def _parse_entreprise(self) -> Optional[str]:
        txt = self._text(".offer-details__where .company")
        return txt

    # ── entrée principale ─────────────────────────────────────────────────────

    def parse(self) -> ParseResult:
        pt = self.page_type()
        if pt != "offer":
            return pt  # "404" ou "waf"

        ld = self._parse_json_ld()
        datas = self._parse_offer_datas()
        code_dept, lieu_libelle, region = self._parse_lieu()

        # ── titre ──
        titre = (
            self._clean(ld.get("title"))
            or self._clean(ld.get("name"))
            or self._text("h1.offer-details__title")
            or self._text("h1")
        )

        # ── description (HTML nettoyé) ──
        desc_raw = self._clean(ld.get("description"))
        if not desc_raw:
            el = self.soup.select_one(".offer-detail_content")
            desc_raw = self._clean(el.get_text()) if el else None

        # ── entreprise ──
        nom_acheteur = (
            self._clean(ld.get("hiringOrganization", {}).get("name"))
            or self._parse_entreprise()
        )

        # ── contrat ──
        contrat_raw = datas.get("contrat") or self._clean(ld.get("employmentType"))
        type_contrat_code = self._CONTRAT_NORM.get((contrat_raw or "").lower())
        type_contrat_libelle = contrat_raw

        # nature du contrat (Temps complet / Temps partiel)
        nature_contrat = datas.get("temps")

        # ── expérience ──
        exp_libelle = datas.get("experience") or self._clean(ld.get("experienceRequirements"))

        # ── qualification / études ──
        qualification_libelle = datas.get("etudes") or self._clean(ld.get("educationRequirements"))

        # ── localisation depuis JSON-LD (plus fiable pour code postal complet) ──
        if ld.get("jobLocation"):
            addr = ld["jobLocation"].get("address", {})
            if not lieu_libelle:
                locality = addr.get("addressLocality", "")
                postal = addr.get("postalCode", "")
                lieu_libelle = self._clean(f"{locality} ({postal})" if postal else locality)
            if not code_dept:
                postal = addr.get("postalCode", "")
                code_dept = postal[:2] if postal else None
            region = region or self._clean(addr.get("addressRegion"))

        # ── date ──
        date_pub = None
        if ld.get("datePosted"):
            date_pub = ld["datePosted"][:10]

        # ── référence ──
        reference = self._parse_reference()
        if not reference and ld.get("identifier"):
            reference = self._clean(str(ld["identifier"].get("name", "")))

        # ── alternance ──
        alternance = (contrat_raw or "").lower() in ("alternance", "apprentissage")

        return LindustrieOffer(
            id=str(self.offer_id),
            titre=titre,
            description=desc_raw,
            type_contrat=type_contrat_code,
            type_contrat_libelle=type_contrat_libelle,
            nature_contrat=nature_contrat,
            experience_exige=None,
            experience_libelle=exp_libelle,
            qualification_libelle=qualification_libelle,
            code_departement=code_dept,
            lieu_travail_libelle=lieu_libelle,
            region=region,
            nom_acheteur=nom_acheteur,
            date_publication=date_pub,
            date_creation=date_pub,
            date_modification=date_pub,
            reference_interne=reference,
            alternance=alternance,
            salaire_libelle=self._parse_salaire(),
            raw_data=ld,
        )


# ─── Gestionnaire de cookie WAF ───────────────────────────────────────────────

class WafCookieManager:
    """Résout le challenge AWS WAF via Playwright et met le cookie en cache."""

    PROBE_URL = "https://www.lindustrie-recrute.fr/candidat/offre/700952"

    def __init__(self):
        self._cookie: Optional[str] = None
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    def _is_expired(self) -> bool:
        return (time.monotonic() - self._fetched_at) > WAF_COOKIE_TTL

    async def get_cookie(self, force: bool = False) -> str:
        async with self._lock:
            if self._cookie is None or self._is_expired() or force:
                self._cookie = await self._resolve_waf()
                self._fetched_at = time.monotonic()
            return self._cookie

    @staticmethod
    async def _resolve_waf() -> str:
        from playwright.async_api import async_playwright

        log.info("Résolution du challenge AWS WAF via Playwright...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=BASE_HEADERS["User-Agent"],
                locale="fr-FR",
            )
            page = await context.new_page()
            await page.goto(
                WafCookieManager.PROBE_URL,
                wait_until="networkidle",
                timeout=40_000,
            )
            try:
                # Attend le contenu réel (body class="paged-...")
                await page.wait_for_function(
                    "document.body.className.includes('paged-')",
                    timeout=20_000,
                )
            except Exception:
                log.warning("WAF : body paged-* non détecté, on continue")

            cookies = await context.cookies()
            await browser.close()

        token = next(
            (c["value"] for c in cookies if "aws-waf-token" in c["name"]),
            None,
        )
        if not token:
            raise RuntimeError(
                "Cookie aws-waf-token introuvable. "
                "Vérifier : playwright install chromium"
            )
        log.info(f"Cookie WAF obtenu ({token[:20]}...)")
        return token


# ─── Scraper principal ────────────────────────────────────────────────────────

class LindustrieScraper:

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

        self._waf = WafCookieManager()
        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore: asyncio.Semaphore
        self._queue: asyncio.Queue
        self._write_lock = asyncio.Lock()

        self.stats = {
            "fetched": 0, "parsed": 0,
            "not_found": 0, "errors": 0, "waf_refresh": 0,
        }

    # ── checkpoint ────────────────────────────────────────────────────────────

    def _load_checkpoint(self) -> int:
        if self.resume and self.checkpoint_path.exists():
            try:
                last = int(self.checkpoint_path.read_text().strip())
                log.info(f"Reprise depuis ID {last + 1}")
                return last + 1
            except ValueError:
                pass
        return self.id_start

    def _save_checkpoint(self, offer_id: int) -> None:
        self.checkpoint_path.write_text(str(offer_id))

    # ── I/O ───────────────────────────────────────────────────────────────────

    async def _write_offer(self, offer: LindustrieOffer) -> None:
        async with self._write_lock:
            with self.output_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(offer.to_dict(), ensure_ascii=False, default=str) + "\n")

    # ── client HTTP ───────────────────────────────────────────────────────────

    async def _build_client(self) -> httpx.AsyncClient:
        cookie = await self._waf.get_cookie()
        headers = {**BASE_HEADERS, "Cookie": f"aws-waf-token={cookie}"}
        return httpx.AsyncClient(headers=headers, follow_redirects=True)

    async def _refresh_client(self) -> None:
        self.stats["waf_refresh"] += 1
        log.warning("Renouvellement du cookie WAF...")
        if self._client:
            await self._client.aclose()
        cookie = await self._waf.get_cookie(force=True)
        headers = {**BASE_HEADERS, "Cookie": f"aws-waf-token={cookie}"}
        self._client = httpx.AsyncClient(headers=headers, follow_redirects=True)
        log.info("Client HTTP reconstruit avec nouveau cookie WAF")

    # ── fetch ─────────────────────────────────────────────────────────────────

    async def _fetch(self, offer_id: int) -> Optional[str]:
        url = BASE_URL.format(id=offer_id)
        for attempt in range(1, RETRY_MAX + 1):
            try:
                await asyncio.sleep(random.uniform(RATE_SLEEP_MIN, RATE_SLEEP_MAX))
                resp = await self._client.get(url, timeout=REQUEST_TIMEOUT)
                if resp.status_code in (200, 202):
                    return resp.text
                if resp.status_code in (404, 410):
                    return None
                if resp.status_code == 429:
                    wait = 15 * attempt
                    log.warning(f"[{offer_id}] 429 – attente {wait}s")
                    await asyncio.sleep(wait)
                    continue
                log.warning(f"[{offer_id}] HTTP {resp.status_code} (attempt {attempt})")
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                log.warning(f"[{offer_id}] {type(e).__name__} attempt {attempt}: {e}")
            if attempt < RETRY_MAX:
                await asyncio.sleep(RETRY_BASE_DELAY ** attempt)
        return None

    # ── worker ────────────────────────────────────────────────────────────────

    async def _worker(self) -> None:
        while True:
            try:
                offer_id: int = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            async with self._semaphore:
                html = await self._fetch(offer_id)

            if html is None:
                self.stats["not_found"] += 1
                self._queue.task_done()
                continue

            self.stats["fetched"] += 1

            try:
                result = LindustrieOfferParser(offer_id, html).parse()

                if result == "waf":
                    log.warning(f"[{offer_id}] WAF détecté → renouvellement cookie")
                    await self._refresh_client()
                    await self._queue.put(offer_id)   # remet en queue
                    self._queue.task_done()
                    continue

                if result == "404":
                    self.stats["not_found"] += 1

                elif isinstance(result, LindustrieOffer) and result.titre:
                    await self._write_offer(result)
                    self.stats["parsed"] += 1
                    self._save_checkpoint(offer_id)
                else:
                    self.stats["not_found"] += 1

            except Exception as e:
                log.error(f"[{offer_id}] Parsing error: {e}", exc_info=True)
                self.stats["errors"] += 1

            self._queue.task_done()

            total = sum(self.stats.values())
            if total % 500 == 0:
                log.info(f"Progression : {self.stats}")

    # ── run ───────────────────────────────────────────────────────────────────

    async def run(self) -> None:
        start_id = self._load_checkpoint()
        total = self.id_end - start_id + 1
        log.info(f"Scraping IDs {start_id} → {self.id_end} ({total} IDs)")

        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._queue = asyncio.Queue()
        for offer_id in range(start_id, self.id_end + 1):
            await self._queue.put(offer_id)

        self._client = await self._build_client()
        t0 = time.monotonic()

        try:
            workers = [asyncio.create_task(self._worker()) for _ in range(self.concurrency)]
            await asyncio.gather(*workers)
        finally:
            await self._client.aclose()

        elapsed = time.monotonic() - t0
        log.info(
            f"Terminé en {elapsed:.1f}s | "
            f"parsés={self.stats['parsed']} | "
            f"not_found={self.stats['not_found']} | "
            f"erreurs={self.stats['errors']} | "
            f"waf_refresh={self.stats['waf_refresh']}"
        )

    def run_sync(self) -> None:
        asyncio.run(self.run())


# ─── Conversion JSONL → Parquet ───────────────────────────────────────────────

def convert_to_parquet(jsonl_path: Path = OUTPUT_JSONL) -> None:
    import duckdb
    out = jsonl_path.with_suffix(".parquet")
    duckdb.connect().execute(f"""
        COPY (SELECT * FROM read_json_auto('{jsonl_path}', ignore_errors=true))
        TO '{out}' (FORMAT PARQUET, COMPRESSION 'zstd')
    """)
    log.info(f"Parquet écrit : {out}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Scraper lindustrie-recrute.fr")
    p.add_argument("--start",       type=int,  default=DEFAULT_ID_START)
    p.add_argument("--end",         type=int,  default=DEFAULT_ID_END)
    p.add_argument("--concurrency", type=int,  default=CONCURRENCY)
    p.add_argument("--output",      type=Path, default=OUTPUT_JSONL)
    p.add_argument("--resume",      action="store_true")
    p.add_argument("--to-parquet",  action="store_true")
    args = p.parse_args()

    if args.to_parquet:
        convert_to_parquet(args.output)
        return

    LindustrieScraper(
        id_start=args.start,
        id_end=args.end,
        output_path=args.output,
        concurrency=args.concurrency,
        resume=args.resume,
    ).run_sync()


if __name__ == "__main__":
    main()