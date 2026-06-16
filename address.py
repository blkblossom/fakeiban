"""
Address generation utilities for the FAKEIBAN API.

Loads address_data.json — one object per country:

    "DE": {
      "country_name": "Germany",
      "phone_format": "+49-XXX-XXXXXXX",
      "streets":   ["Hauptstraße", ...],
      "locations": [{"city": "München", "region": "Bayern", "postcode": "80331"}, ...]
    }

Each location is a real (city, region, postcode) tuple sourced from GeoNames, so
the generated city/region/postcode are always a genuine, consistent combination.
The street is a real street name for that country plus a random house number.

Usage:
    gen = AddressGenerator(JSON_URL)
    gen.load()
    result = gen.generate("DE")   # AddressResult dataclass
    payload = result.to_dict()
"""
from __future__ import annotations

import json
import random
import urllib.request
from dataclasses import dataclass, asdict


NAME_POOLS = {
    "germanic": {
        "first": ["Lukas", "Leon", "Felix", "Maximilian", "Jonas", "Paul", "Elias", "Finn", "Noah", "Ben",
                  "Anna", "Lena", "Marie", "Sophie", "Laura", "Hannah", "Mia", "Emilia", "Lea", "Klara"],
        "last": ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Wagner", "Becker", "Hoffmann", "Schäfer", "Bauer",
                 "Koch", "Richter", "Klein", "Wolf", "Schröder", "Neumann", "Braun", "Zimmermann", "Krüger", "Hartmann"],
    },
    "dutch": {
        "first": ["Daan", "Sem", "Lucas", "Finn", "Bram", "Lars", "Thijs", "Jesse", "Tim", "Ruben",
                  "Emma", "Julia", "Sophie", "Mila", "Tess", "Sara", "Lotte", "Anna", "Eva", "Fleur"],
        "last": ["de Jong", "Jansen", "de Vries", "van den Berg", "van Dijk", "Bakker", "Visser", "Smit", "Meijer", "Mulder",
                 "de Boer", "Bos", "Vos", "Peters", "Hendriks", "van Leeuwen", "Dekker", "Brouwer", "de Wit", "Dijkstra"],
    },
    "french": {
        "first": ["Lucas", "Hugo", "Louis", "Jules", "Gabriel", "Arthur", "Raphaël", "Paul", "Nathan", "Théo",
                  "Emma", "Léa", "Chloé", "Manon", "Camille", "Sarah", "Inès", "Jade", "Louise", "Alice"],
        "last": ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Petit", "Durand", "Leroy", "Moreau", "Simon",
                 "Laurent", "Lefebvre", "Michel", "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier", "Girard"],
    },
    "italian": {
        "first": ["Francesco", "Alessandro", "Lorenzo", "Matteo", "Andrea", "Gabriele", "Riccardo", "Tommaso", "Marco", "Davide",
                  "Giulia", "Sofia", "Aurora", "Alice", "Chiara", "Martina", "Sara", "Giorgia", "Emma", "Elena"],
        "last": ["Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo", "Ricci", "Marino", "Greco",
                 "Bruno", "Gallo", "Conti", "De Luca", "Costa", "Giordano", "Mancini", "Rizzo", "Lombardi", "Moretti"],
    },
    "spanish": {
        "first": ["Hugo", "Martín", "Lucas", "Mateo", "Daniel", "Pablo", "Alejandro", "Álvaro", "Adrián", "David",
                  "Lucía", "Sofía", "María", "Martina", "Paula", "Valeria", "Carmen", "Elena", "Laura", "Ana"],
        "last": ["García", "Fernández", "González", "Rodríguez", "López", "Martínez", "Sánchez", "Pérez", "Gómez", "Díaz",
                 "Ruiz", "Hernández", "Jiménez", "Moreno", "Muñoz", "Álvarez", "Romero", "Alonso", "Navarro", "Torres"],
    },
    "portuguese": {
        "first": ["João", "Francisco", "Santiago", "Afonso", "Duarte", "Tomás", "Rodrigo", "Martim", "Gonçalo", "Diogo",
                  "Maria", "Leonor", "Matilde", "Beatriz", "Mariana", "Carolina", "Ana", "Inês", "Sofia", "Margarida"],
        "last": ["Silva", "Santos", "Ferreira", "Pereira", "Oliveira", "Costa", "Rodrigues", "Martins", "Sousa", "Fernandes",
                 "Gomes", "Lopes", "Marques", "Almeida", "Ribeiro", "Carvalho", "Teixeira", "Moreira", "Correia", "Pinto"],
    },
    "nordic": {
        "first": ["William", "Oscar", "Liam", "Emil", "Noah", "Lucas", "Elias", "Aksel", "Henrik", "Mathias",
                  "Emma", "Alma", "Ella", "Maja", "Olivia", "Saga", "Nora", "Frida", "Astrid", "Ingrid"],
        "last": ["Hansen", "Johansen", "Andersen", "Nielsen", "Larsen", "Karlsson", "Johansson", "Andersson", "Berg", "Lind",
                 "Nilsson", "Eriksson", "Olsen", "Pedersen", "Kristiansen", "Lindberg", "Bergström", "Holm", "Dahl", "Pettersen"],
    },
    "baltic": {
        "first": ["Jonas", "Matas", "Lukas", "Markus", "Rasmus", "Kristjan", "Artūrs", "Roberts", "Tomas", "Dovydas",
                  "Emilija", "Liepa", "Ieva", "Laura", "Greta", "Anete", "Liis", "Kaisa", "Gabija", "Austėja"],
        "last": ["Kazlauskas", "Petrauskas", "Bērziņš", "Kalniņš", "Tamm", "Saar", "Mägi", "Vītols", "Ozols", "Jansons",
                 "Jankauskas", "Stankevičius", "Liiv", "Kask", "Rebane", "Bērzkalns", "Kukk", "Kivi", "Ozoliņš", "Krūmiņš"],
    },
    "slavic": {
        "first": ["Jan", "Jakub", "Filip", "Marek", "Tomáš", "Petr", "Luka", "Stefan", "Nikola", "Miloš",
                  "Anna", "Eva", "Maria", "Petra", "Katarina", "Jana", "Milica", "Ana", "Lucia", "Tereza"],
        "last": ["Novák", "Kovač", "Horvat", "Nowak", "Kowalski", "Petrović", "Jovanović", "Ivanov", "Popov", "Marković",
                 "Wójcik", "Svoboda", "Dvořák", "Nikolić", "Đorđević", "Kozłowski", "Kučera", "Veselý", "Sokolov", "Wiśniewski"],
    },
    "romanian": {
        "first": ["Andrei", "Mihai", "Alexandru", "Gabriel", "Ștefan", "Cristian", "Florin", "Ionuț", "Vlad", "Răzvan",
                  "Maria", "Elena", "Ioana", "Andreea", "Ana", "Cristina", "Gabriela", "Alexandra", "Diana", "Bianca"],
        "last": ["Popescu", "Ionescu", "Popa", "Radu", "Dumitru", "Stan", "Gheorghe", "Constantin", "Marin", "Stoica",
                 "Munteanu", "Matei", "Ciobanu", "Florea", "Georgescu", "Tudor", "Barbu", "Nistor", "Dragomir", "Lungu"],
    },
    "hungarian": {
        "first": ["Bence", "Máté", "Levente", "Dávid", "Ádám", "Marcell", "Dániel", "Balázs", "Gergő", "Zsombor",
                  "Hanna", "Anna", "Zsófia", "Léna", "Emma", "Lili", "Nóra", "Réka", "Petra", "Boglárka"],
        "last": ["Nagy", "Kovács", "Tóth", "Szabó", "Horváth", "Varga", "Kiss", "Molnár", "Németh", "Farkas",
                 "Balogh", "Papp", "Takács", "Juhász", "Lakatos", "Mészáros", "Oláh", "Simon", "Rácz", "Fekete"],
    },
    "greek": {
        "first": ["Georgios", "Dimitris", "Konstantinos", "Nikos", "Yannis", "Vasilis", "Christos", "Panagiotis", "Kostas", "Stavros",
                  "Maria", "Eleni", "Katerina", "Sofia", "Georgia", "Dimitra", "Vasiliki", "Ioanna", "Anastasia", "Despina"],
        "last": ["Papadopoulos", "Papadakis", "Vlachos", "Georgiou", "Nikolaou", "Pappas", "Antoniou", "Makris", "Dimitriou", "Oikonomou",
                 "Konstantinidis", "Ioannidis", "Vasileiou", "Angelopoulos", "Christodoulou", "Petridis", "Karagiannis", "Samaras", "Spanos", "Christou"],
    },
    "english": {
        "first": ["Oliver", "George", "Harry", "Jack", "Charlie", "Noah", "Jacob", "Thomas", "Oscar", "William",
                  "Olivia", "Amelia", "Isla", "Ava", "Emily", "Sophie", "Grace", "Mia", "Poppy", "Charlotte"],
        "last": ["Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Evans", "Thomas", "Roberts", "Walker",
                 "Wright", "Robinson", "Thompson", "White", "Hughes", "Edwards", "Green", "Hall", "Wood", "Harris"],
    },
    "arabic": {
        "first": ["Mohammed", "Ahmed", "Ali", "Omar", "Khaled", "Yusuf", "Hamza", "Khalid", "Tariq", "Saif",
                  "Fatima", "Aisha", "Mariam", "Layla", "Noor", "Huda", "Salma", "Yasmin", "Rania", "Amira"],
        "last": ["Al-Sayed", "Al-Mansour", "Hassan", "Ibrahim", "Khalil", "Al-Farsi", "Haddad", "Saleh", "Nasser", "Aziz",
                 "Al-Rashid", "Al-Ahmad", "Mansour", "Al-Hashimi", "Darwish", "Al-Najjar", "Younis", "Al-Khatib", "Suleiman", "Al-Amin"],
    },
    "turkic": {
        "first": ["Yusuf", "Mehmet", "Mustafa", "Emre", "Burak", "Ahmet", "Murat", "Can", "Kerem", "Eren",
                  "Zeynep", "Elif", "Aylin", "Leyla", "Ayşe", "Merve", "Ece", "Defne", "Selin", "Esra"],
        "last": ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Aydın", "Öztürk", "Arslan", "Doğan",
                 "Kılıç", "Aslan", "Çetin", "Koç", "Kurt", "Özdemir", "Şimşek", "Polat", "Korkmaz", "Erdoğan"],
    },
    "latam": {
        "first": ["Santiago", "Mateo", "Sebastián", "Diego", "Nicolás", "Samuel", "Benjamín", "Emiliano", "Daniel", "Tomás",
                  "Valentina", "Camila", "Sofía", "Isabella", "Lucía", "Mariana", "Valeria", "Daniela", "Gabriela", "Antonella"],
        "last": ["González", "Rodríguez", "Hernández", "López", "Martínez", "Pérez", "Ramírez", "Torres", "Flores", "Rivera",
                 "Gómez", "Díaz", "Cruz", "Morales", "Reyes", "Gutiérrez", "Ortiz", "Castillo", "Vargas", "Mendoza"],
    },
    "hebrew": {
        "first": ["Noam", "Itai", "Yosef", "David", "Eitan", "Ariel", "Daniel", "Omer", "Yonatan", "Lior",
                  "Tamar", "Noa", "Maya", "Yael", "Shira", "Talia", "Avigail", "Hila", "Adi", "Roni"],
        "last": ["Cohen", "Levi", "Mizrahi", "Peretz", "Biton", "Avraham", "Friedman", "Katz", "Shapiro", "Azoulay",
                 "Dahan", "Malka", "Gabbay", "Ben-David", "Amar", "Shalom", "Hadad", "Elbaz", "Barak", "Segal"],
    },
    "urdu": {
        "first": ["Muhammad", "Ahmed", "Ali", "Hassan", "Bilal", "Usman", "Hamza", "Faisal", "Imran", "Saad",
                  "Ayesha", "Fatima", "Zainab", "Maryam", "Hina", "Sana", "Amna", "Iqra", "Nadia", "Sara"],
        "last": ["Khan", "Malik", "Sheikh", "Hussain", "Iqbal", "Raza", "Butt", "Qureshi", "Chaudhry", "Awan",
                 "Ahmad", "Ali", "Shah", "Aslam", "Akhtar", "Javed", "Nawaz", "Farooq", "Siddiqui", "Bhatti"],
    },
}

REGION_COUNTRIES = {
    "germanic": ["DE", "AT", "CH", "LI", "LU"],
    "dutch": ["NL", "BE"],
    "french": ["FR", "MC"],
    "italian": ["IT"],
    "spanish": ["ES", "AD"],
    "portuguese": ["PT"],
    "nordic": ["DK", "NO", "SE", "FI", "IS"],
    "baltic": ["EE", "LV", "LT"],
    "slavic": ["PL", "CZ", "SK", "SI", "HR", "RS", "BA", "ME", "BG", "RU", "UA", "MD"],
    "romanian": ["RO"],
    "hungarian": ["HU"],
    "greek": ["GR", "CY"],
    "english": ["GB", "IE", "GI", "VG", "LC", "MT", "SC", "MU"],
    "arabic": ["AE", "BH", "JO", "KW", "QA", "PS"],
    "turkic": ["TR", "AZ", "KZ", "GE"],
    "latam": ["DO", "GT", "HN", "NI", "SV", "CR"],
    "hebrew": ["IL"],
    "urdu": ["PK"],
}

COUNTRY_NAME_REGION = {cc: region for region, ccs in REGION_COUNTRIES.items() for cc in ccs}


def random_name(country_code: str) -> str:
    pool = NAME_POOLS[COUNTRY_NAME_REGION.get(country_code, "english")]
    return f"{random.choice(pool['first'])} {random.choice(pool['last'])}"


@dataclass(frozen=True)
class AddressResult:
    country_code: str
    country_name: str
    full_name: str
    street: str
    city: str
    region: str
    postcode: str
    phone: str

    def to_dict(self) -> dict:
        return asdict(self)


class UnknownAddressCountryError(ValueError):
    """Raised when generate() is called with an unsupported country code."""


class AddressGenerator:
    """Loads per-country address data (JSON) and generates real, consistent
    addresses — same load/loaded/countries/generate/to_dict shape as IBANGenerator."""

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
        locations = d.get("locations") if d else None
        if not locations:
            raise UnknownAddressCountryError(
                f"Unknown or unsupported country code: {country}")

        loc = random.choice(locations)           # real city + region + postcode
        streets = d.get("streets", [])
        street_name = random.choice(streets) if streets else ""
        house = random.randint(1, 9999)
        street = f"{house} {street_name}" if street_name else str(house)

        return AddressResult(
            country_code=cc,
            country_name=d.get("country_name", cc),
            full_name=random_name(cc),
            street=street,
            city=loc["city"],
            region=loc["region"],
            postcode=loc["postcode"],
            phone=self.phone(d),
        )

    def fetch(self, url: str) -> str:
        with urllib.request.urlopen(url, timeout=self.fetch_timeout) as r:
            return r.read().decode("utf-8")

    @staticmethod
    def phone(d: dict) -> str:
        fmt = d.get("phone_format", "+X-XXX-XXX-XXXX")
        number = "".join(str(random.randint(0, 9)) if ch == "X" else ch for ch in fmt)
        return number.replace("-", "").replace(" ", "")
