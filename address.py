"""
Address generation utilities for the FAKEIBAN API.

Loads address_data.json — one self-contained object per country:

    "DE": {
      "country_name": "Germany",
      "phone_format": "+49-XXX-XXXXXXX",
      "streets":      ["Hauptstraße", ...],
      "cities":       [{"name": "Munich", "region": "Bavaria", "postcode": "80331"},
                       {"name": "Berlin"}],          # region/postcode optional
      "regions":      ["Bavaria", "Berlin", ...],
      "street_addresses": [...]                      # optional landmarks
    }

A city may carry its own region+postcode (a real, consistent pair) — used
together when present; otherwise the region is picked from the country's region
list and the postcode is generated to the local format.

Usage:
    gen = AddressGenerator(JSON_URL)
    gen.load()
    result = gen.generate("DE")   # AddressResult dataclass
    payload = result.to_dict()
"""
from __future__ import annotations

import json
import random
import string
import urllib.request
from dataclasses import dataclass, asdict

ALPHANUMERIC_POSTCODE = {"GB", "NL"}


@dataclass(frozen=True)
class AddressResult:
    country_code: str
    country_name: str
    street: str
    street_address: str
    city: str
    region: str
    postcode: str
    phone: str

    def to_dict(self) -> dict:
        return asdict(self)


class UnknownAddressCountryError(ValueError):
    """Raised when generate() is called with an unsupported country code."""


class AddressGenerator:
    """Loads per-country address data (JSON) and generates plausible addresses —
    same load/loaded/countries/generate/to_dict shape as IBANGenerator."""

    def __init__(self, json_url: str, fetch_timeout: float = 5.0) -> None:
        self.json_url = json_url
        self.fetch_timeout = fetch_timeout
        self.data: dict[str, dict] = {}

    @property
    def loaded(self) -> bool:
        return bool(self.data)

    @property
    def countries(self) -> list[dict]:
        return sorted(
            ({"country_code": cc, "country_name": d.get("country_name", cc)}
             for cc, d in self.data.items()),
            key=lambda x: x["country_code"],
        )

    def load(self) -> None:
        self.data = json.loads(self.fetch(self.json_url))
        if not self.data:
            raise RuntimeError("Loaded address data is empty")

    def generate(self, country: str) -> AddressResult:
        cc = country.strip().upper()
        d = self.data.get(cc)
        if d is None:
            raise UnknownAddressCountryError(
                f"Unknown or unsupported country code: {country}")

        cities = d.get("cities", [])
        if cities:
            city = random.choice(cities)
            city_name = city["name"]
            region = city.get("region") or self.random_region(d)
            postcode = city.get("postcode") or self.random_postcode(cc)
        else:
            city_name = ""
            region = self.random_region(d)
            postcode = self.random_postcode(cc)

        streets = d.get("streets", [])
        street_name = random.choice(streets) if streets else ""
        house = random.randint(1, 9999)
        street = f"{house} {street_name}" if street_name else str(house)

        landmarks = d.get("street_addresses", [])
        street_address = random.choice(landmarks) if landmarks else ""

        return AddressResult(
            country_code=cc,
            country_name=d.get("country_name", cc),
            street=street,
            street_address=street_address,
            city=city_name,
            region=region,
            postcode=postcode,
            phone=self.phone(d),
        )

    def fetch(self, url: str) -> str:
        with urllib.request.urlopen(url, timeout=self.fetch_timeout) as r:
            return r.read().decode("utf-8")

    @staticmethod
    def random_region(d: dict) -> str:
        regions = d.get("regions", [])
        return random.choice(regions) if regions else ""

    @staticmethod
    def random_postcode(cc: str) -> str:
        if cc in ALPHANUMERIC_POSTCODE:
            L = string.ascii_uppercase
            return (f"{random.choice(L)}{random.choice(L)}{random.randint(0, 9)} "
                    f"{random.randint(0, 9)}{random.choice(L)}{random.choice(L)}")
        return str(random.randint(10000, 99999))

    @staticmethod
    def phone(d: dict) -> str:
        fmt = d.get("phone_format", "+X-XXX-XXX-XXXX")
        return "".join(str(random.randint(0, 9)) if ch == "X" else ch for ch in fmt)
