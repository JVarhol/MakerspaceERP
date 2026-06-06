import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter

from ..schemas import BarcodeLookupResult, UrlMetaResult

router = APIRouter(prefix="/api", tags=["barcode"])

HEADERS = {"User-Agent": "MakerspaceERP/1.1 (+home-lab)"}

SUPPLIER_MAP = {
    "amazon.com": "Amazon",
    "amazon.co": "Amazon",
    "amzn.to": "Amazon",
    "aliexpress.com": "AliExpress",
    "digikey.com": "DigiKey",
    "mouser.com": "Mouser",
    "newark.com": "Newark",
    "adafruit.com": "Adafruit",
    "sparkfun.com": "SparkFun",
    "lcsc.com": "LCSC",
    "octopart.com": "Octopart",
    "ebay.com": "eBay",
    "mcmaster.com": "McMaster-Carr",
}


def _detect_supplier(url: str) -> Optional[str]:
    for domain, name in SUPPLIER_MAP.items():
        if domain in url:
            return name
    return None


async def _lookup_openfoodfacts(barcode: str) -> Optional[BarcodeLookupResult]:
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    try:
        async with httpx.AsyncClient(timeout=5, headers=HEADERS) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return None
            data = r.json()
            if data.get("status") != 1:
                return None
            product = data.get("product", {})
            name = product.get("product_name") or product.get("product_name_en")
            if not name:
                return None
            return BarcodeLookupResult(
                barcode=barcode,
                name=name,
                description=product.get("categories", ""),
                image_url=product.get("image_url"),
                source="Open Food Facts",
            )
    except Exception:
        return None


async def _lookup_upcitemdb(barcode: str) -> Optional[BarcodeLookupResult]:
    url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={barcode}"
    try:
        async with httpx.AsyncClient(timeout=5, headers=HEADERS) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return None
            data = r.json()
            items = data.get("items", [])
            if not items:
                return None
            item = items[0]
            return BarcodeLookupResult(
                barcode=barcode,
                name=item.get("title"),
                description=item.get("description"),
                image_url=(item.get("images") or [None])[0],
                source="UPC Item DB",
            )
    except Exception:
        return None


@router.get("/barcode/lookup/{barcode}", response_model=BarcodeLookupResult)
async def lookup_barcode(barcode: str):
    result = await _lookup_openfoodfacts(barcode)
    if result:
        return result
    result = await _lookup_upcitemdb(barcode)
    if result:
        return result
    return BarcodeLookupResult(barcode=barcode, source=None)


@router.get("/url/metadata", response_model=UrlMetaResult)
@router.post("/url/metadata", response_model=UrlMetaResult)
async def get_url_metadata(url: str):
    supplier = _detect_supplier(url)
    title = None
    price = None
    try:
        async with httpx.AsyncClient(
            timeout=8,
            headers={**HEADERS, "Accept-Language": "en-US,en;q=0.9"},
            follow_redirects=True,
        ) as client:
            r = await client.get(url)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                og_title = soup.find("meta", property="og:title")
                if og_title and og_title.get("content"):
                    title = og_title["content"].strip()
                elif soup.title:
                    title = soup.title.string.strip() if soup.title.string else None
                price_meta = (
                    soup.find("meta", property="product:price:amount")
                    or soup.find("meta", {"itemprop": "price"})
                )
                if price_meta:
                    try:
                        raw = price_meta.get("content", "")
                        price = float(re.sub(r"[^\d.]", "", raw))
                    except (ValueError, TypeError):
                        pass
    except Exception:
        pass
    return UrlMetaResult(url=url, title=title, supplier_name=supplier, price=price)
