import scrapy
import re
from scrapy_playwright.page import PageMethod
from CheckPII_Scraper.items import PersonItem

# playwright-stealth patches fingerprinting vectors that expose headless browsers:
# navigator.webdriver, canvas/WebGL fingerprint, plugin list, Chrome runtime, etc.
import sys

# Add user site-packages to path so pip --user installs are found
import site
user_site = site.getusersitepackages()
if user_site not in sys.path:
    sys.path.insert(0, user_site)

# Try tf-playwright-stealth first (keeps original stealth_async API),
# then fall back to playwright-stealth 2.x new API,
# then fall back to no stealth (manual JS patches still apply)
STEALTH_AVAILABLE = False
stealth_async = None

try:
    # tf-playwright-stealth — install with: pip install --user tf-playwright-stealth
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
    print("[Spider] playwright-stealth loaded OK (tf-playwright-stealth)")
except ImportError:
    try:
        # playwright-stealth 2.x new API
        from playwright_stealth import Stealth as _Stealth
        async def stealth_async(page):
            await _Stealth().apply_stealth_async(page)
        STEALTH_AVAILABLE = True
        print("[Spider] playwright-stealth loaded OK (v2.x Stealth class)")
    except ImportError:
        print("[Spider] WARNING: No stealth library found.")
        print("[Spider] Install with: pip install --user tf-playwright-stealth")
        print("[Spider] Manual JS patches will still apply.")


# ══════════════════════════════════════════════════════════════════════
# NAME VALIDATOR
# Prevents garbage like "New York", "View Profile", "Age Range",
# "Ontario Canada", "United States" from being saved as person names.
# ══════════════════════════════════════════════════════════════════════

# Known non-name words that appear as capitalized text on broker pages
_INVALID_NAME_WORDS = {
    # US states (full names)
    'alabama','alaska','arizona','arkansas','california','colorado',
    'connecticut','delaware','florida','georgia','hawaii','idaho',
    'illinois','indiana','iowa','kansas','kentucky','louisiana','maine',
    'maryland','massachusetts','michigan','minnesota','mississippi',
    'missouri','montana','nebraska','nevada','hampshire','jersey',
    'mexico','york','carolina','dakota','ohio','oklahoma','oregon',
    'pennsylvania','rhode','island','tennessee','texas','utah','vermont',
    'virginia','washington','wisconsin','wyoming',

    # Canadian provinces (full names)
    'alberta','columbia','manitoba','brunswick','newfoundland','labrador',
    'nova','scotia','ontario','edward','quebec','saskatchewan','yukon',
    'northwest','territories','nunavut',

    # Countries
    'united','states','canada','america','kingdom','england','scotland',
    'wales','ireland','australia','zealand',

    # UK regions
    'london','england','scotland','wales','cornwall','yorkshire',
    'lancashire','midlands','suffolk','norfolk','essex','kent','surrey',

    # Australian states
    'south','wales','victoria','queensland','australia','tasmania',

    # City words that appear as capitalized pairs
    'new','los','san','las','saint','fort','mount','port','east','west',
    'north','south','upper','lower','central','greater',

    # UI text commonly scraped by mistake
    'view','profile','page','search','filter','next','prev','previous',
    'more','results','show','hide','click','here','login','sign','up',
    'register','free','report','background','check','people','person',
    'find','name','last','first','middle','age','range','city','state',
    'country','address','phone','email','contact','info','information',
    'data','record','listing','entry','result','member','user','account',
    'privacy','policy','terms','service','copyright','all','rights',
    'reserved','loading','please','wait','error','sorry','not','found',
    'unknown','none','null','undefined','true','false',

    # Common website navigation words
    'home','about','us','help','faq','support','blog','news','press',
    'careers','jobs','advertise','partners','affiliate','sitemap',
}

# These patterns indicate the text is NOT a person's name
_INVALID_NAME_PATTERNS = [
    re.compile(r'\d'),                          # contains digits: "John 123"
    re.compile(r'[^\w\s\-\'\.]'),               # special chars: "John@Doe"
    re.compile(r'\b(llc|inc|corp|ltd|co)\b', re.IGNORECASE),  # business names
    re.compile(r'(street|avenue|road|drive|blvd|lane|court|place|way)\b', re.IGNORECASE),  # addresses
    re.compile(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b', re.IGNORECASE),
    re.compile(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', re.IGNORECASE),
    re.compile(r'^(mr|mrs|ms|dr|prof|rev)\.?\s', re.IGNORECASE),  # titles without name
    re.compile(r'\.com|\.org|\.net|\.ca|\.co\.uk', re.IGNORECASE),  # URLs
    re.compile(r'@'),                           # email addresses
]

# Valid name characters — letters, spaces, hyphens, apostrophes, dots
_VALID_NAME_CHARS = re.compile(r"^[A-Za-z\s\-'\.]+$")

# A real first or last name is typically 2-25 chars, starts with a letter
_VALID_NAME_PART  = re.compile(r"^[A-Za-z][a-zA-Z'\-\.]{1,24}$")


def is_valid_person_name(full_name: str) -> bool:
    """
    Returns True if full_name looks like a real person's name.
    Returns False if it looks like a place, UI element, or garbage.
    """
    if not full_name:
        return False

    name = full_name.strip()

    # Must be between 4 and 60 characters
    if not (4 <= len(name) <= 60):
        return False

    # Must contain only valid name characters
    if not _VALID_NAME_CHARS.match(name):
        return False

    # Must have at least 2 parts (first + last)
    parts = name.split()
    if len(parts) < 2:
        return False

    # No part should be a single character (except initials like "J.")
    for part in parts:
        clean = part.strip(".'")
        if len(clean) < 2:
            continue  # allow initials
        if not _VALID_NAME_PART.match(part):
            return False

    # Check for invalid pattern matches
    for pattern in _INVALID_NAME_PATTERNS:
        if pattern.search(name):
            return False

    # Check if any word is a known non-name word
    # We allow some common words IF they appear alongside a clearly personal name
    # e.g. "Mary May" is valid, "New York" is not
    lower_parts = [p.lower().strip(".'") for p in parts]
    invalid_count = sum(1 for p in lower_parts if p in _INVALID_NAME_WORDS)

    # If MORE THAN HALF the words are invalid, reject
    if invalid_count > len(parts) / 2:
        return False

    # Must have at least one part that looks like a typical name
    # (starts uppercase, rest lowercase or mixed — not ALL CAPS)
    has_proper_case = any(
        p[0].isupper() and not p.isupper()
        for p in parts if len(p) > 1
    )
    # Allow ALL CAPS names since some brokers store them that way
    # but reject if every part is a single uppercase letter
    all_initials = all(len(p) == 1 for p in parts)
    if all_initials:
        return False

    return True


def clean_name(full_name: str) -> tuple[str, str, str]:
    """
    Cleans and splits a full name into (full, first, last).
    Handles: "JOHN SMITH", "Smith, John", "John A. Smith"
    """
    name = full_name.strip()

    # Handle "Last, First" format
    if ',' in name:
        parts = name.split(',', 1)
        last  = parts[0].strip().title()
        first = parts[1].strip().title()
        return f"{first} {last}", first, last

    # Title-case if all uppercase
    if name.isupper():
        name = name.title()

    parts = name.split()
    if len(parts) >= 2:
        first = parts[0]
        last  = parts[-1]
        return name, first, last

    return name, name, ""


class BrokerSpider(scrapy.Spider):
    """
    Bulk spider using Playwright to bypass bot detection.
    Covers US, Canada, UK, Australia and Global brokers.

    Run single broker:   scrapy crawl broker_spider -a broker_id=1
    With resume:         scrapy crawl broker_spider -a broker_id=1 -s JOBDIR=crawls/spokeo-1
    Parallel:            run_all_spiders.bat
    """

    name = "broker_spider"

    # ── Region codes ───────────────────────────────────────────────────
    CA_PROVINCES = {'AB','BC','MB','NB','NL','NS','NT','NU','ON','PE','QC','SK','YT'}
    US_STATES    = {
        'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL',
        'IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT',
        'NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI',
        'SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY'
    }
    UK_REGIONS   = {
        'ENG','SCT','WLS','NIR',                    # UK nations
        'LONDON','ENGLAND','SCOTLAND','WALES',       # common text forms
    }
    AU_STATES    = {'NSW','VIC','QLD','WA','SA','TAS','ACT','NT'}

    # ── Page counter for memory management ────────────────────────────
    # Restart browser context every N pages to prevent memory leak
    PAGES_BEFORE_CONTEXT_RESTART = 500

    BROKER_CONFIGS = {
        # ── US ─────────────────────────────────────────────────────────
        1: {
            "name": "Spokeo", "country": "US",
            "start_urls": [
                "https://www.spokeo.com/people/A0001",
                "https://www.spokeo.com/people/B0001",
                "https://www.spokeo.com/people/C0001",
                "https://www.spokeo.com/people/D0001",
                "https://www.spokeo.com/people/EF0001",
                "https://www.spokeo.com/people/G0001",
                "https://www.spokeo.com/people/H0001",
                "https://www.spokeo.com/people/IJ0001",
                "https://www.spokeo.com/people/K0001",
                "https://www.spokeo.com/people/L0001",
                "https://www.spokeo.com/people/M0001",
                "https://www.spokeo.com/people/NO0001",
                "https://www.spokeo.com/people/P0001",
                "https://www.spokeo.com/people/QR0001",
                "https://www.spokeo.com/people/S0001",
                "https://www.spokeo.com/people/TUV0001",
                "https://www.spokeo.com/people/WXYZ0001",
            ],
            "type": "spokeo",
        },
        2: {
            "name": "Whitepages", "country": "US",
            "start_urls": ["https://www.whitepages.com/people"],
            "type": "generic", "next_page": "a[rel='next']",
        },
        3: {
            "name": "BeenVerified", "country": "US",
            "start_urls": ["https://www.beenverified.com/people-search/"],
            "type": "generic", "next_page": "a.pagination-next",
        },
        4: {
            "name": "PeopleFinder", "country": "US",
            "start_urls": ["https://www.peoplefinders.com/people/"],
            "type": "generic", "next_page": "a.next",
        },
        5: {
            "name": "MyLife", "country": "US",
            "start_urls": ["https://www.mylife.com/people-search/"],
            "type": "generic", "next_page": "a.next-page",
        },
        6: {
            "name": "Intelius", "country": "US",
            "start_urls": ["https://www.intelius.com/people-search/"],
            "type": "generic", "next_page": "a[aria-label='Next']",
        },
        7: {
            "name": "Radaris US", "country": "US",
            "start_urls": ["https://radaris.com/p/"],
            "type": "generic", "next_page": "a.next",
        },
        8: {
            "name": "TruthFinder", "country": "US",
            "start_urls": ["https://www.truthfinder.com/people-search/"],
            "type": "generic", "next_page": "a.pagination__next",
        },
        9: {
            "name": "Instantcheckmate", "country": "US",
            "start_urls": ["https://www.instantcheckmate.com/people-search/"],
            "type": "generic", "next_page": "a.next",
        },
        10: {
            "name": "USPhoneBook", "country": "US",
            "start_urls": ["https://www.usphonebook.com/"],
            "type": "generic", "next_page": "a.next",
        },

        # ── Canada ─────────────────────────────────────────────────────
        11: {
            "name": "Canada411", "country": "CA",
            "start_urls": [
                f"https://www.canada411.ca/search/pers/2/{l}/"
                for l in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            ],
            "type": "canada411",
        },
        12: {
            "name": "Radaris Canada", "country": "CA",
            "start_urls": ["https://ca.radaris.com/p/"],
            "type": "generic", "next_page": "a.next",
        },
        13: {
            "name": "Whitepages CA", "country": "CA",
            "start_urls": ["https://www.whitepages.ca/"],
            "type": "generic", "next_page": "a[rel='next']",
        },
        14: {
            "name": "411.ca", "country": "CA",
            "start_urls": [
                "https://www.411.ca/person/on/",
                "https://www.411.ca/person/bc/",
                "https://www.411.ca/person/ab/",
                "https://www.411.ca/person/qc/",
                "https://www.411.ca/person/mb/",
                "https://www.411.ca/person/sk/",
                "https://www.411.ca/person/ns/",
                "https://www.411.ca/person/nb/",
                "https://www.411.ca/person/nl/",
                "https://www.411.ca/person/pe/",
            ],
            "type": "ca_411",
        },
        15: {
            "name": "CanadaPages", "country": "CA",
            "start_urls": ["https://www.canadapages.com/people/"],
            "type": "generic", "next_page": "a.next",
        },

        # ── United Kingdom ─────────────────────────────────────────────
        16: {
            "name": "BT Phone Book", "country": "GB",
            "start_urls": ["https://www.thephonebook.bt.com/Person/"],
            "type": "generic", "next_page": "a[rel='next']",
        },
        17: {
            "name": "192.com", "country": "GB",
            # 192.com has an alphabetical directory of surnames
            "start_urls": [
                f"https://www.192.com/people/{l}/"
                for l in "abcdefghijklmnopqrstuvwxyz"
            ],
            "type": "192com",
            "next_page": "a.next",
        },

        # ── Australia ──────────────────────────────────────────────────
        18: {
            "name": "White Pages AU", "country": "AU",
            "start_urls": [
                f"https://www.whitepages.com.au/residential?initial={l}"
                for l in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            ],
            "type": "generic",
            "next_page": "a[aria-label='Next page']",
        },

        # ── Global ─────────────────────────────────────────────────────
        19: {
            "name": "Pipl", "country": "GLOBAL",
            "start_urls": ["https://pipl.com/"],
            "type": "generic", "next_page": "a.next",
        },

        # ══════════════════════════════════════════════════════════════
        # NEW TIER-1 BROKERS — JSON-LD structured data, no paywall
        # ══════════════════════════════════════════════════════════════

        # TruePeopleSearch — embeds full Person JSON-LD with phone + email
        # Alphabetical directory: /details?name=any&rid=0x1 increments in hex
        20: {
            "name": "TruePeopleSearch", "country": "US",
            "start_urls": [
                f"https://www.truepeoplesearch.com/results?name={first}+{last}&citystatezip="
                for first in ["John","Mary","James","Robert","Patricia",
                               "Michael","Jennifer","William","Linda","David",
                               "Elizabeth","Richard","Barbara","Joseph","Susan",
                               "Thomas","Jessica","Charles","Sarah","Christopher"]
                for last in ["Smith","Johnson","Williams","Brown","Jones",
                              "Garcia","Miller","Davis","Wilson","Anderson",
                              "Taylor","Thomas","Jackson","White","Harris",
                              "Martin","Thompson","Moore","Young","Allen"]
            ],
            "type": "truepeoplesearch",
        },

        # FastPeopleSearch — same JSON-LD approach as TruePeopleSearch
        21: {
            "name": "FastPeopleSearch", "country": "US",
            "start_urls": [
                f"https://www.fastpeoplesearch.com/name/{first}-{last}"
                for first in ["John","Mary","James","Robert","Patricia",
                               "Michael","Jennifer","William","Linda","David"]
                for last in ["Smith","Johnson","Williams","Brown","Jones",
                              "Garcia","Miller","Davis","Wilson","Anderson"]
            ],
            "type": "fastpeoplesearch",
        },

        # ZabaSearch — minimal protection, free names/phones/addresses
        22: {
            "name": "ZabaSearch", "country": "US",
            "start_urls": [
                f"https://www.zabasearch.com/people/{l}/"
                for l in "abcdefghijklmnopqrstuvwxyz"
            ],
            "type": "zabasearch",
        },

        # ThatsThem — free public records, name/phone/email/address
        23: {
            "name": "ThatsThem", "country": "US",
            "start_urls": [
                f"https://thatsthem.com/name/{first}-{last}"
                for first in ["John","Mary","James","Robert","Michael",
                               "William","David","Richard","Joseph","Thomas"]
                for last in ["Smith","Johnson","Williams","Brown","Jones",
                              "Garcia","Miller","Davis","Wilson","Anderson"]
            ],
            "type": "thatsthem",
        },

        # FamilyTreeNow — genealogy data, low bot protection
        # Good for relatives and address history
        24: {
            "name": "FamilyTreeNow", "country": "US",
            "start_urls": [
                f"https://www.familytreenow.com/search/genealogy/results?first={first}&last={last}"
                for first in ["John","Mary","James","Robert","Michael",
                               "William","David","Richard","Joseph","Thomas"]
                for last in ["Smith","Johnson","Williams","Brown","Jones",
                              "Garcia","Miller","Davis","Wilson","Anderson"]
            ],
            "type": "familytreenow",
        },

        # AnyWho — classic AT&T directory, minimal protection
        25: {
            "name": "AnyWho", "country": "US",
            "start_urls": [
                f"https://www.anywho.com/whitepages/{first}+{last}/us"
                for first in ["John","Mary","James","Robert","Michael",
                               "William","David","Richard","Joseph","Thomas"]
                for last in ["Smith","Johnson","Williams","Brown","Jones",
                              "Garcia","Miller","Davis","Wilson","Anderson"]
            ],
            "type": "anywho",
        },

        # PeekYou — social media aggregator, no paywall
        26: {
            "name": "PeekYou", "country": "US",
            "start_urls": [
                f"https://www.peekyou.com/{first}_{last}"
                for first in ["john","mary","james","robert","michael",
                               "william","david","richard","joseph","thomas"]
                for last in ["smith","johnson","williams","brown","jones",
                              "garcia","miller","davis","wilson","anderson"]
            ],
            "type": "peekyou",
        },
    }

    def __init__(self, broker_id=1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.broker_id   = int(broker_id)
        self.config      = self.BROKER_CONFIGS.get(self.broker_id, {})
        self.start_urls  = self.config.get("start_urls", [])
        self.country     = self.config.get("country", "US")
        self.page_count  = 0  # tracks pages for memory management
        print(f"[Spider] Starting — Broker: {self.config.get('name')} "
              f"(ID {self.broker_id}) Country: {self.country}")

    # ── Playwright request helper ──────────────────────────────────────
    def _pw_request(self, url, callback, **kwargs):
        """
        Creates a Scrapy request using Playwright with stealth patches applied.
        Stealth mode patches all known browser fingerprinting vectors so the
        browser looks identical to a real Chrome user visiting the page.
        Rotates browser context every PAGES_BEFORE_CONTEXT_RESTART pages
        to prevent the JavaScript heap out-of-memory crash.
        """
        self.page_count += 1
        context_name = f"ctx_{(self.page_count // self.PAGES_BEFORE_CONTEXT_RESTART)}"

        return scrapy.Request(
            url,
            callback=callback,
            meta={
                "playwright":              True,
                "playwright_context":      context_name,
                # True so we can access the page in the async parse method
                "playwright_include_page": True,
                "playwright_page_goto_kwargs": {
                    "wait_until": "domcontentloaded",
                    "timeout":    60000,
                },
                # PageMethods run after navigation — scroll and wait for content
                "playwright_page_methods": [
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight / 2)"),
                    PageMethod("wait_for_timeout", 800),
                ],
            },
            errback=self.handle_error,
            **kwargs,
        )

    async def _stealth_page_init(self, page):
        """
        Apply all stealth patches to a Playwright page before use.
        This patches the following fingerprinting vectors:
          - navigator.webdriver → false
          - navigator.plugins   → spoofed real browser plugins
          - navigator.languages → realistic values
          - canvas fingerprint  → randomized per session
          - WebGL fingerprint   → randomized per session
          - Chrome runtime      → injected to match real Chrome
          - Permissions API     → patched
          - window.outerWidth/Height → realistic values
          - User-Agent via CDP  → consistent with browser headers
        """
        if STEALTH_AVAILABLE:
            await stealth_async(page)

        # Additional manual patches on top of stealth library
        await page.evaluate("""() => {
            // Remove any remaining webdriver traces
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });

            // Spoof realistic screen dimensions
            Object.defineProperty(screen, 'width',       { get: () => 1920 });
            Object.defineProperty(screen, 'height',      { get: () => 1080 });
            Object.defineProperty(screen, 'availWidth',  { get: () => 1920 });
            Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
            Object.defineProperty(screen, 'colorDepth',  { get: () => 24   });
            Object.defineProperty(screen, 'pixelDepth',  { get: () => 24   });

            // Make window dimensions look real
            Object.defineProperty(window, 'outerWidth',  { get: () => 1920 });
            Object.defineProperty(window, 'outerHeight', { get: () => 1080 });
            Object.defineProperty(window, 'innerWidth',  { get: () => 1920 });
            Object.defineProperty(window, 'innerHeight', { get: () => 1080 });

            // Spoof realistic hardware concurrency (CPU cores)
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });

            // Spoof realistic device memory
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

            // Remove automation-related properties
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

            // Spoof realistic connection info
            if (navigator.connection) {
                Object.defineProperty(navigator.connection, 'rtt', { get: () => 50 });
            }
        }""")

        # Human-like random mouse movement before page loads
        import random
        await page.mouse.move(
            random.randint(100, 800),
            random.randint(100, 600)
        )

    # ── Entry point ────────────────────────────────────────────────────
    async def start(self):
        for url in self.start_urls:
            yield self._pw_request(url, callback=self.parse)

    async def parse(self, response):
        # Apply stealth patches to the live page object then close it.
        # The rendered HTML is already in response.text — we just need
        # to patch the page before Cloudflare challenge scripts run.
        page = response.meta.get("playwright_page")
        if page:
            try:
                await self._stealth_page_init(page)
            except Exception as e:
                print(f"[Spider] Stealth patch error: {e}")
            finally:
                await page.close()

        # Dispatch to the correct sync parser.
        # async generators can't use yield from — iterate manually instead.
        print(f"[Spider] Page: {response.url} | Status: {response.status}")
        broker_type = self.config.get("type", "generic")

        dispatch = {
            "spokeo":           self.parse_spokeo_index,
            "canada411":        self.parse_canada411,
            "ca_411":           self.parse_ca_411,
            "192com":           self.parse_192com,
            "truepeoplesearch": self.parse_truepeoplesearch,
            "fastpeoplesearch": self.parse_fastpeoplesearch,
            "zabasearch":       self.parse_zabasearch,
            "thatsthem":        self.parse_thatsthem,
            "familytreenow":    self.parse_familytreenow,
            "anywho":           self.parse_anywho,
            "peekyou":          self.parse_peekyou,
        }

        parser = dispatch.get(broker_type, self.parse_listings)
        for item in parser(response):
            yield item

    # ══════════════════════════════════════════════════════════════════
    # SPOKEO (US)
    # ══════════════════════════════════════════════════════════════════

    def parse_spokeo_index(self, response):
        all_links  = response.css("a::attr(href)").getall()
        name_links = [
            l for l in all_links
            if l and re.match(r'^/[A-Z][a-zA-Z]+-[A-Z][a-zA-Z]+$', l)
        ]
        print(f"[Spider] Spokeo index {response.url} — {len(name_links)} name links")
        for link in name_links:
            yield self._pw_request(response.urljoin(link), callback=self.parse_spokeo_namepage)
        next_page = response.css("a[rel='next']::attr(href)").get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_spokeo_index)

    def parse_spokeo_namepage(self, response):
        url_path   = response.url.rstrip("/").split("/")[-1]
        name_parts = url_path.split("-")
        first_name = name_parts[0] if name_parts else ""
        last_name  = name_parts[-1] if len(name_parts) > 1 else ""
        full_name  = f"{first_name} {last_name}".strip()

        # ── Validate the name extracted from the URL ───────────────────
        if not is_valid_person_name(full_name):
            return
        full_name, first_name, last_name = clean_name(full_name)

        entries = response.css(
            "li.name-list-item, div.name-list-item, "
            "div[class*='result'], div[class*='card'], "
            "article[class*='result'], ul.person-list > li"
        )
        print(f"[Spider] Spokeo '{full_name}' — {len(entries)} entries")

        if entries:
            for entry in entries:
                item = self._build_item(entry, full_name, first_name, last_name, response.url)
                if item:
                    yield item
        else:
            yield from self.parse_spokeo_text(response, full_name, first_name, last_name)

        next_page = response.css("a[rel='next']::attr(href)").get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_spokeo_namepage)

    def parse_spokeo_text(self, response, full_name, first_name, last_name):
        text        = response.text
        loc_pattern = re.compile(r'([A-Z][a-zA-Z\s]{2,25}),\s*([A-Z]{2})\b')
        age_pattern = re.compile(r'\bage\s*:?\s*(\d{1,3})\b', re.IGNORECASE)
        locations   = list(set(loc_pattern.findall(text)))[:20]
        ages        = age_pattern.findall(text)

        if not locations:
            locations = [("", "")]

        for i, (raw_city, raw_region) in enumerate(locations):
            age     = self._validate_age(ages[i] if i < len(ages) else None)
            city    = self._validate_city(raw_city)
            region  = self._validate_region(raw_region)
            country = self._detect_country(raw_region) if raw_region else self.country

            # Only yield if we have at least a valid city or region
            if city or region:
                yield self._make_item(full_name, first_name, last_name, age,
                                      response.url, city or "", region or "", '', country)

    # ══════════════════════════════════════════════════════════════════
    # CANADA411
    # ══════════════════════════════════════════════════════════════════

    def parse_canada411(self, response):
        all_links  = response.css("a::attr(href)").getall()
        name_links = [
            l for l in all_links
            if l and re.match(r'^/name/[A-Za-z]+-[A-Za-z]+/', l)
        ]
        print(f"[Spider] Canada411 {response.url} — {len(name_links)} name links")
        for link in name_links:
            yield self._pw_request(response.urljoin(link), callback=self.parse_canada411_namepage)
        next_page = response.css("a.next::attr(href), a[rel='next']::attr(href)").get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_canada411)

    def parse_canada411_namepage(self, response):
        url_path   = response.url.rstrip("/").split("/")[-1]
        parts      = url_path.split("-")
        last_name  = parts[0] if parts else ""
        first_name = parts[1] if len(parts) > 1 else ""
        full_name  = f"{first_name} {last_name}".strip()

        entries = response.css(
            "div.result, li.result, div[class*='listing'], div[class*='person'], article"
        )
        if entries:
            for entry in entries:
                item = self._build_item(entry, full_name, first_name, last_name,
                                        response.url, default_country="CA")
                if item:
                    yield item
        else:
            yield from self.parse_by_text(response, default_country="CA")

        next_page = response.css("a.next::attr(href)").get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_canada411_namepage)

    # ══════════════════════════════════════════════════════════════════
    # 411.CA
    # ══════════════════════════════════════════════════════════════════

    def parse_ca_411(self, response):
        entries = response.css(
            "div.person, li.person, div[class*='result'], div[class*='listing'], article"
        )
        print(f"[Spider] 411.ca {response.url} — {len(entries)} entries")
        if entries:
            for entry in entries:
                item = self._parse_listing(entry, response.url, default_country="CA")
                if item:
                    yield item
        else:
            yield from self.parse_by_text(response, default_country="CA")
        next_page = response.css("a.next::attr(href), a[rel='next']::attr(href)").get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_ca_411)

    # ══════════════════════════════════════════════════════════════════
    # 192.COM (UK)
    # ══════════════════════════════════════════════════════════════════

    def parse_192com(self, response):
        """192.com UK people directory"""
        entries = response.css(
            "div.person-result, li.person-result, div[class*='result'], "
            "div[class*='person'], article, li.listing"
        )
        print(f"[Spider] 192.com {response.url} — {len(entries)} entries")
        if entries:
            for entry in entries:
                item = self._parse_listing(entry, response.url, default_country="GB")
                if item:
                    yield item
        else:
            yield from self.parse_by_text(response, default_country="GB")
        next_page = response.css("a.next::attr(href), a[rel='next']::attr(href)").get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_192com)

    # ══════════════════════════════════════════════════════════════════
    # JSON-LD HELPER
    # Many modern broker sites embed Person schema in <script> tags.
    # This is the cleanest data source — structured, validated by the
    # site itself, and no CSS selector guessing needed.
    # ══════════════════════════════════════════════════════════════════

    def _extract_jsonld(self, response) -> list[dict]:
        """
        Extracts all JSON-LD blocks from a page and returns them as a list.
        Handles multiple <script type="application/ld+json"> tags.
        """
        import json
        results = []
        for script in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(script)
                # Handle both single objects and arrays
                if isinstance(data, list):
                    results.extend(data)
                else:
                    results.append(data)
            except (json.JSONDecodeError, ValueError):
                continue
        return results

    def _item_from_jsonld_person(self, person: dict, page_url: str) -> PersonItem | None:
        """
        Builds a PersonItem from a JSON-LD Person object.
        Schema reference: https://schema.org/Person

        Handles fields: name, givenName, familyName, age, telephone,
        email, address, knows, worksFor, jobTitle, sameAs (social profiles)
        """
        # ── Name ──────────────────────────────────────────────────────
        full_name  = (person.get('name') or '').strip()
        first_name = (person.get('givenName') or '').strip()
        last_name  = (person.get('familyName') or '').strip()

        if not full_name and first_name and last_name:
            full_name = f"{first_name} {last_name}"
        elif full_name and not first_name:
            full_name, first_name, last_name = clean_name(full_name)

        if not is_valid_person_name(full_name):
            return None

        full_name, first_name, last_name = clean_name(full_name)

        # ── Age ───────────────────────────────────────────────────────
        age = self._validate_age(person.get('age') or person.get('birthDate'))

        # ── Address ───────────────────────────────────────────────────
        addresses = []
        addr_data = person.get('address') or person.get('homeLocation')
        if addr_data:
            if isinstance(addr_data, list):
                addr_list = addr_data
            else:
                addr_list = [addr_data]

            for addr in addr_list:
                if isinstance(addr, str):
                    raw_city, raw_region, raw_postal = self._split_location(addr)
                    city   = self._validate_city(raw_city)
                    region = self._validate_region(raw_region)
                    postal = self._validate_postal(raw_postal, self._detect_country(raw_region))
                else:
                    city   = self._validate_city(addr.get('addressLocality') or addr.get('city') or '')
                    region = self._validate_region(addr.get('addressRegion') or addr.get('state') or '')
                    postal = self._validate_postal(
                        addr.get('postalCode') or addr.get('zipCode') or '',
                        self._detect_country(addr.get('addressRegion') or '')
                    )
                country = self._detect_country(region or '')
                if city or region:
                    addresses.append({
                        'address':     addr.get('streetAddress', '') if isinstance(addr, dict) else '',
                        'city':        city   or '',
                        'state':       region or '',
                        'postal_code': postal or '',
                        'country':     country,
                        'is_current':  len(addresses) == 0,
                    })

        # ── Phones ────────────────────────────────────────────────────
        phones    = []
        phone_raw = person.get('telephone') or person.get('phone') or []
        if isinstance(phone_raw, str):
            phone_raw = [phone_raw]
        for p in phone_raw:
            cleaned = self._validate_phone(str(p))
            if cleaned:
                phones.append({'phone': cleaned, 'type': self._classify_phone(cleaned)})

        # ── Emails ────────────────────────────────────────────────────
        emails    = []
        email_raw = person.get('email') or []
        if isinstance(email_raw, str):
            email_raw = [email_raw]
        for e in email_raw:
            cleaned = self._validate_email(str(e))
            if cleaned:
                emails.append(cleaned)

        # ── Relatives ─────────────────────────────────────────────────
        relatives = []
        knows_raw = person.get('knows') or person.get('relatedTo') or []
        if isinstance(knows_raw, dict):
            knows_raw = [knows_raw]
        for k in knows_raw:
            rel_name = k.get('name', '') if isinstance(k, dict) else str(k)
            validated = self._validate_relative_name(rel_name)
            if validated:
                relatives.append({'name': validated, 'relation': k.get('relationshipType', 'associate') if isinstance(k, dict) else 'associate'})

        # ── Employment ────────────────────────────────────────────────
        employment = []
        works_for  = person.get('worksFor') or person.get('affiliation')
        job_title  = person.get('jobTitle') or ''
        if works_for or job_title:
            employer  = self._validate_employer(works_for.get('name', '') if isinstance(works_for, dict) else str(works_for or ''))
            job_title = self._validate_job_title(str(job_title))
            if employer or job_title:
                employment.append({'employer': employer or '', 'job_title': job_title or '', 'income_range': ''})

        # ── Social profiles ───────────────────────────────────────────
        socials  = []
        same_as  = person.get('sameAs') or []
        if isinstance(same_as, str):
            same_as = [same_as]
        for url in same_as:
            clean_url = self._validate_url(str(url))
            if clean_url:
                for domain, platform in self._SOCIAL_DOMAINS.items():
                    if domain in clean_url:
                        username = clean_url.rstrip('/').split('/')[-1]
                        socials.append({'platform': platform, 'profile_url': clean_url, 'username': username})

        item = PersonItem()
        item['broker_id']       = self.broker_id
        item['broker_name']     = self.config.get('name', '')
        item['broker_url']      = self.start_urls[0] if self.start_urls else ''
        item['listing_url']     = page_url
        item['full_name']       = full_name
        item['first_name']      = first_name
        item['last_name']       = last_name
        item['age']             = age
        item['addresses']       = addresses
        item['phone_numbers']   = phones
        item['email_addresses'] = emails
        item['relatives']       = relatives
        item['employment']      = employment
        item['social_profiles'] = socials
        return item

    # ══════════════════════════════════════════════════════════════════
    # TRUEPEOPLESEARCH
    # Embeds full Person JSON-LD with phone, email, address, relatives
    # ══════════════════════════════════════════════════════════════════

    def parse_truepeoplesearch(self, response):
        """
        TruePeopleSearch embeds a ProfilePage JSON-LD with nested Person
        objects containing name, address, phone, email, and relatives.
        """
        print(f"[Spider] TruePeopleSearch {response.url} | Status: {response.status}")
        found = 0

        for block in self._extract_jsonld(response):
            # Top-level Person
            if block.get('@type') == 'Person':
                item = self._item_from_jsonld_person(block, response.url)
                if item:
                    found += 1
                    yield item

            # ProfilePage wrapping a Person
            elif block.get('@type') == 'ProfilePage':
                person = block.get('mainEntity') or block.get('about') or {}
                if isinstance(person, dict):
                    item = self._item_from_jsonld_person(person, response.url)
                    if item:
                        found += 1
                        yield item

            # ItemList of Persons
            elif block.get('@type') == 'ItemList':
                for element in (block.get('itemListElement') or []):
                    person = element.get('item') or element
                    if isinstance(person, dict):
                        item = self._item_from_jsonld_person(person, response.url)
                        if item:
                            found += 1
                            yield item

        # Fallback to HTML if no JSON-LD found
        if found == 0:
            print(f"[Spider] TruePeopleSearch no JSON-LD on {response.url} — HTML fallback")
            yield from self.parse_by_text(response)

        # Next page
        next_page = response.css("a[aria-label='Next']::attr(href), a.next::attr(href)").get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_truepeoplesearch)

    # ══════════════════════════════════════════════════════════════════
    # FASTPEOPLESEARCH
    # Same JSON-LD approach — Person schema + FAQPage for emails
    # ══════════════════════════════════════════════════════════════════

    def parse_fastpeoplesearch(self, response):
        """
        FastPeopleSearch uses Person JSON-LD for core data and a
        FAQPage JSON-LD block where emails are stored in answer text.
        """
        import json, re as _re
        print(f"[Spider] FastPeopleSearch {response.url} | Status: {response.status}")
        found    = 0
        emails   = []

        # First pass — collect any emails from FAQPage blocks
        for block in self._extract_jsonld(response):
            if block.get('@type') == 'FAQPage':
                for qa in (block.get('mainEntity') or []):
                    answer_text = ''
                    answer      = qa.get('acceptedAnswer') or {}
                    if isinstance(answer, dict):
                        answer_text = answer.get('text') or ''
                    # Extract emails from answer text
                    for match in _re.findall(
                        r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                        answer_text
                    ):
                        cleaned = self._validate_email(match)
                        if cleaned:
                            emails.append(cleaned)

        # Second pass — extract Person objects
        for block in self._extract_jsonld(response):
            btype = block.get('@type', '')
            person = None
            if btype == 'Person':
                person = block
            elif btype in ('ProfilePage', 'WebPage'):
                person = block.get('mainEntity') or block.get('about')

            if isinstance(person, dict):
                item = self._item_from_jsonld_person(person, response.url)
                if item:
                    # Attach any FAQPage emails found
                    existing = {e for e in item.get('email_addresses', [])}
                    for e in emails:
                        if e not in existing:
                            item['email_addresses'].append(e)
                            existing.add(e)
                    found += 1
                    yield item

        if found == 0:
            yield from self.parse_by_text(response)

        next_page = response.css("a[rel='next']::attr(href), a.next::attr(href)").get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_fastpeoplesearch)

    # ══════════════════════════════════════════════════════════════════
    # ZABASEARCH
    # Classic directory — minimal protection, simple HTML structure
    # ══════════════════════════════════════════════════════════════════

    def parse_zabasearch(self, response):
        """
        ZabaSearch uses a simple alphabetical people directory.
        Data is in plain HTML — name, city, state, phone number.
        """
        print(f"[Spider] ZabaSearch {response.url} | Status: {response.status}")

        # Try JSON-LD first
        found = 0
        for block in self._extract_jsonld(response):
            if block.get('@type') == 'Person':
                item = self._item_from_jsonld_person(block, response.url)
                if item:
                    found += 1
                    yield item

        if found > 0:
            return

        # HTML fallback — ZabaSearch result rows
        entries = response.css(
            "div.peoplebox, div.person_box, div[class*='person'], "
            "li.person, div.results-row, tr.person-row"
        )
        if entries:
            print(f"[Spider] ZabaSearch {len(entries)} entries via HTML")
            for entry in entries:
                item = self._parse_listing(entry, response.url, default_country='US')
                if item:
                    yield item
        else:
            yield from self.parse_by_text(response, default_country='US')

        # Follow name links to individual pages
        name_links = [
            l for l in response.css("a::attr(href)").getall()
            if l and '/people/' in l and l != response.url
        ]
        for link in name_links[:50]:  # cap at 50 per page
            yield self._pw_request(response.urljoin(link), callback=self.parse_zabasearch)

        next_page = response.css("a[rel='next']::attr(href), a.next::attr(href)").get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_zabasearch)

    # ══════════════════════════════════════════════════════════════════
    # THATSTHEM
    # Public records aggregator — name, phone, email, address
    # ══════════════════════════════════════════════════════════════════

    def parse_thatsthem(self, response):
        """
        ThatsThem uses Person JSON-LD and also has accessible HTML.
        Often exposes phone and email without a paywall.
        """
        print(f"[Spider] ThatsThem {response.url} | Status: {response.status}")
        found = 0

        for block in self._extract_jsonld(response):
            btype  = block.get('@type', '')
            person = None
            if btype == 'Person':
                person = block
            elif btype in ('ProfilePage', 'WebPage', 'ItemPage'):
                person = block.get('mainEntity') or block.get('about')

            if isinstance(person, dict):
                item = self._item_from_jsonld_person(person, response.url)
                if item:
                    found += 1
                    yield item

        if found == 0:
            entries = response.css(
                "div.person-result, div.result-person, "
                "article[class*='person'], li[class*='person']"
            )
            if entries:
                for entry in entries:
                    item = self._parse_listing(entry, response.url, default_country='US')
                    if item:
                        yield item
            else:
                yield from self.parse_by_text(response, default_country='US')

        next_page = response.css("a[rel='next']::attr(href), a.next::attr(href)").get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_thatsthem)

    # ══════════════════════════════════════════════════════════════════
    # FAMILYTREENOW
    # Genealogy data — good for relatives and address history
    # Low bot protection, public records focus
    # ══════════════════════════════════════════════════════════════════

    def parse_familytreenow(self, response):
        """
        FamilyTreeNow exposes names, ages, addresses, and relative
        connections via both JSON-LD and HTML. Genealogy focus means
        richer relative/family data than typical people-search sites.
        """
        print(f"[Spider] FamilyTreeNow {response.url} | Status: {response.status}")
        found = 0

        for block in self._extract_jsonld(response):
            if block.get('@type') in ('Person', 'FamilyMember'):
                item = self._item_from_jsonld_person(block, response.url)
                if item:
                    found += 1
                    yield item

        if found == 0:
            entries = response.css(
                "div.card-person, div[class*='result'], "
                "li.person-result, div.person-item"
            )
            for entry in entries:
                item = self._parse_listing(entry, response.url, default_country='US')
                if item:
                    yield item
                    found += 1

        if found == 0:
            yield from self.parse_by_text(response, default_country='US')

        next_page = response.css("a[rel='next']::attr(href), a.next::attr(href), "
                                  "a[aria-label='Next']::attr(href)").get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_familytreenow)

    # ══════════════════════════════════════════════════════════════════
    # ANYWHO
    # Classic AT&T white pages directory — minimal protection
    # ══════════════════════════════════════════════════════════════════

    def parse_anywho(self, response):
        """
        AnyWho (AT&T directory) has basic HTML structure.
        Returns name, address, phone from verified carrier data.
        """
        print(f"[Spider] AnyWho {response.url} | Status: {response.status}")
        found = 0

        # Try JSON-LD first
        for block in self._extract_jsonld(response):
            if block.get('@type') == 'Person':
                item = self._item_from_jsonld_person(block, response.url)
                if item:
                    found += 1
                    yield item

        if found == 0:
            entries = response.css(
                "div.result, li.result, div[class*='listing'], "
                "div[class*='person'], div.card, article"
            )
            if entries:
                for entry in entries:
                    item = self._parse_listing(entry, response.url, default_country='US')
                    if item:
                        yield item
                        found += 1
            else:
                yield from self.parse_by_text(response, default_country='US')

        next_page = response.css("a[rel='next']::attr(href), a.next::attr(href)").get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_anywho)

    # ══════════════════════════════════════════════════════════════════
    # PEEKYOU
    # Social media aggregator — no paywall, focuses on online presence
    # ══════════════════════════════════════════════════════════════════

    def parse_peekyou(self, response):
        """
        PeekYou aggregates social profiles and online presence.
        No paywall on core data. Good source for social profile links.
        JSON-LD Person schema + HTML result cards both work.
        """
        print(f"[Spider] PeekYou {response.url} | Status: {response.status}")
        found = 0

        # JSON-LD first
        for block in self._extract_jsonld(response):
            btype  = block.get('@type', '')
            person = None
            if btype == 'Person':
                person = block
            elif btype in ('ProfilePage', 'WebPage'):
                person = block.get('mainEntity') or block.get('about')

            if isinstance(person, dict):
                item = self._item_from_jsonld_person(person, response.url)
                if item:
                    found += 1
                    yield item

        if found == 0:
            entries = response.css(
                "li.m_card, div.m_card, div[class*='result'], "
                "li[class*='person'], div[class*='person-card']"
            )
            for entry in entries:
                # PeekYou shows name + social links in result cards
                item = self._parse_listing(entry, response.url, default_country='US')
                if item:
                    # Also grab any social links in the card
                    item['social_profiles'] = self._parse_socials(entry)
                    found += 1
                    yield item

        if found == 0:
            yield from self.parse_by_text(response, default_country='US')

        next_page = response.css(
            "a[rel='next']::attr(href), a.next::attr(href), "
            "a[aria-label='Next page']::attr(href)"
        ).get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_peekyou)

    # ══════════════════════════════════════════════════════════════════
    # GENERIC (most brokers)
    # ══════════════════════════════════════════════════════════════════

    def parse_listings(self, response):
        selectors_to_try = [
            "div[data-testid='serp-result-card']",
            "div.result--v2", "li.name-list-item", "div.name-list-item",
            "div.card", "article.result", "div.person-card",
            "div.search-result", "div[class*='PersonCard']",
            "div[class*='person-result']", "div[class*='result-card']",
            "li[class*='person']",
        ]
        listings        = []
        default_country = self.config.get("country", "US")

        for selector in selectors_to_try:
            listings = response.css(selector)
            if listings:
                print(f"[Spider] Matched '{selector}' — {len(listings)} listings")
                break

        if not listings:
            print(f"[Spider] No selector matched on {response.url} — text scan")
            yield from self.parse_by_text(response, default_country=default_country)
            return

        for listing in listings:
            item = self._parse_listing(listing, response.url, default_country=default_country)
            if item:
                yield item

        next_sel  = self.config.get("next_page", "a[rel='next']")
        next_page = response.css(f"{next_sel}::attr(href)").get()
        if next_page:
            yield self._pw_request(response.urljoin(next_page), callback=self.parse_listings)

    # ══════════════════════════════════════════════════════════════════
    # ITEM BUILDERS
    # ══════════════════════════════════════════════════════════════════

    def _build_item(self, sel, full_name, first_name, last_name,
                    page_url, default_country=None):
        if default_country is None:
            default_country = self.country

        age_raw     = sel.css("[class*='age']::text, .age::text").get() or ""
        age         = self._validate_age(self._extract_age(age_raw) or age_raw)
        listing_url = sel.css("a::attr(href)").get() or page_url
        if listing_url and not listing_url.startswith("http"):
            listing_url = self.start_urls[0].rstrip("/") + "/" + listing_url.lstrip("/")

        # ── Enhanced phone extraction ──────────────────────────────────
        # Brokers like Spokeo blur/lock phone numbers. We try multiple
        # selectors and patterns to catch any that are visible.
        phones = self._parse_phones_enhanced(sel)

        # ── Enhanced email extraction ──────────────────────────────────
        emails = self._parse_emails_enhanced(sel)

        item = PersonItem()
        item['broker_id']       = self.broker_id
        item['broker_name']     = self.config.get('name', '')
        item['broker_url']      = self.start_urls[0] if self.start_urls else ''
        item['listing_url']     = listing_url
        item['full_name']       = full_name
        item['first_name']      = first_name
        item['last_name']       = last_name
        item['age']             = age
        item['addresses']       = self._parse_addresses(sel, default_country)
        item['phone_numbers']   = phones
        item['email_addresses'] = emails
        item['relatives']       = self._parse_relatives(sel)
        item['employment']      = self._parse_employment(sel)
        item['social_profiles'] = self._parse_socials(sel)
        return item

    def _make_item(self, full_name, first_name, last_name, age,
                   url, city, region, postal, country):
        item = PersonItem()
        item['broker_id']       = self.broker_id
        item['broker_name']     = self.config.get('name', '')
        item['broker_url']      = self.start_urls[0] if self.start_urls else ''
        item['listing_url']     = url
        item['full_name']       = full_name
        item['first_name']      = first_name
        item['last_name']       = last_name
        item['age']             = age
        item['addresses']       = [{'address':'','city':city,'state':region,
                                     'postal_code':postal,'country':country,
                                     'is_current':True}] if city else []
        item['phone_numbers']   = []
        item['email_addresses'] = []
        item['relatives']       = []
        item['employment']      = []
        item['social_profiles'] = []
        return item

    def _parse_listing(self, sel, page_url, default_country=None):
        if default_country is None:
            default_country = self.country

        full_name = (
            sel.css("a::text, h2::text, h3::text, .name::text, "
                    "[class*='name']::text, strong::text").get() or ""
        ).strip()

        # ── Validate before doing anything else ────────────────────────
        if not is_valid_person_name(full_name):
            return None

        full_name, first_name, last_name = clean_name(full_name)
        return self._build_item(sel, full_name, first_name, last_name,
                                 page_url, default_country)

    # ── Text scan fallback ─────────────────────────────────────────────
    def parse_by_text(self, response, default_country=None):
        if default_country is None:
            default_country = self.country

        name_pattern  = re.compile(r'\b([A-Z][a-z]{1,20})\s+([A-Z][a-z]{1,20})\b')
        loc_pattern   = re.compile(r'([A-Za-z\s]{3,30}),\s*([A-Z]{2})\s*([\w\d]{3,7})?')
        phone_pattern = re.compile(r'[\+\d][\d\s\-\(\)\.]{7,15}')
        email_pattern = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

        text   = response.text
        names  = name_pattern.findall(text)
        locs   = loc_pattern.findall(text)
        phones = [re.sub(r'[^\d\+]', '', m) for m in phone_pattern.findall(text) if len(re.sub(r'[^\d\+]', '', m)) >= 7]
        emails = list(set(email_pattern.findall(text)))
        seen   = set()

        for i, (first, last) in enumerate(names[:100]):
            full = f"{first} {last}"

            # ── Validate before saving ─────────────────────────────────
            if not is_valid_person_name(full):
                continue

            if full in seen:
                continue
            seen.add(full)

            full, first, last = clean_name(full)
            loc     = locs[0] if locs else ('', '', '')
            country = self._detect_country(loc[1]) if loc[1] else default_country

            item = self._make_item(full, first, last, None,
                                   response.url, loc[0].strip(),
                                   loc[1], loc[2] or '', country)
            if phones:
                item['phone_numbers'] = [{"phone": p, "type": "unknown"} for p in phones[:3]]
            if emails:
                item['email_addresses'] = emails[:3]
            yield item

    # ══════════════════════════════════════════════════════════════════
    # FIELD VALIDATORS
    # Each validator returns the cleaned value or None if invalid.
    # Nothing reaches the database without passing its validator.
    # ══════════════════════════════════════════════════════════════════

    # ── Known valid region codes ───────────────────────────────────────
    _ALL_VALID_REGIONS = (
        # US states
        {'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL',
         'IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT',
         'NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI',
         'SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'} |
        # Canadian provinces
        {'AB','BC','MB','NB','NL','NS','NT','NU','ON','PE','QC','SK','YT'} |
        # Australian states
        {'NSW','VIC','QLD','WA','SA','TAS','ACT','NT'} |
        # UK nations/regions
        {'ENG','SCT','WLS','NIR'}
    )

    # ── Known invalid city/region words (not actual place names) ──────
    _NOT_A_CITY = {
        'unknown','none','null','undefined','n/a','na','not','available',
        'view','profile','click','here','more','results','loading','please',
        'wait','error','search','find','people','person','name','address',
        'phone','email','age','range','data','record','listing','result',
        'information','info','details','contact','privacy','policy','terms',
        'service','copyright','all','rights','reserved','free','report',
        'background','check','member','user','account','register','login',
        'sign','up','home','about','help','faq','support','blog','news',
    }

    # ── Postal code patterns per country ──────────────────────────────
    _POSTAL_PATTERNS = {
        'CA': re.compile(r'^[A-Z]\d[A-Z]\s?\d[A-Z]\d$'),          # M5V 1A1
        'US': re.compile(r'^\d{5}(-\d{4})?$'),                     # 78701 or 78701-1234
        'GB': re.compile(r'^[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}$'),  # SW1A 2AA
        'AU': re.compile(r'^\d{4}$'),                              # 2000
    }

    # ── Known fake/test phone numbers to reject ────────────────────────
    _FAKE_PHONE_PATTERNS = [
        re.compile(r'^(\d)\1{6,}$'),          # all same digit: 1111111
        re.compile(r'^(123456|654321)'),       # sequential test numbers
        re.compile(r'^(555)'),                 # US fake 555 numbers (fictional)
        re.compile(r'^0{7,}'),                 # all zeros
    ]

    # ── Valid social media domains ─────────────────────────────────────
    _SOCIAL_DOMAINS = {
        'facebook.com':  'Facebook',
        'twitter.com':   'Twitter',
        'x.com':         'X (Twitter)',
        'linkedin.com':  'LinkedIn',
        'instagram.com': 'Instagram',
        'tiktok.com':    'TikTok',
        'youtube.com':   'YouTube',
        'pinterest.com': 'Pinterest',
        'snapchat.com':  'Snapchat',
        'reddit.com':    'Reddit',
    }

    def _validate_phone(self, raw: str) -> str | None:
        """
        Returns a cleaned E.164-style phone string, or None if invalid.
        Accepts: +1-416-555-1234, (416) 555-1234, 4165551234, +44 20 7946 0958
        Rejects: too short, all same digit, obvious fakes, zip codes
        """
        if not raw:
            return None

        # Strip everything except digits and leading +
        digits = re.sub(r'[^\d\+]', '', raw.strip())

        # Handle tel: prefix
        digits = digits.replace('tel:', '')

        # Must be 7–15 digits (ITU-T E.164 max is 15)
        digit_only = digits.lstrip('+')
        if not (7 <= len(digit_only) <= 15):
            return None

        # Reject if all same digit
        if len(set(digit_only)) == 1:
            return None

        # Reject known fake patterns
        for pattern in self._FAKE_PHONE_PATTERNS:
            if pattern.match(digit_only):
                return None

        # Reject if it looks like a zip code (exactly 5 digits, US zip range)
        if re.match(r'^\d{5}$', digit_only):
            return None

        # Reject if it looks like a year (4 digits, 1900–2099)
        if re.match(r'^(19|20)\d{2}$', digit_only):
            return None

        return digits  # return cleaned version with + if present

    def _classify_phone(self, digits: str) -> str:
        """Classify phone as mobile, landline, or unknown based on prefix."""
        d = digits.lstrip('+')
        # North American mobile prefixes (rough heuristic)
        if re.match(r'^1[2-9]\d{2}[2-9]\d{6}$', d):
            return 'unknown'  # can't reliably distinguish without lookup
        return 'unknown'

    def _validate_email(self, raw: str) -> str | None:
        """
        Returns cleaned email or None if invalid.
        Rejects: missing @, missing TLD, too short, obvious placeholders.
        """
        if not raw:
            return None

        email = raw.strip().lower()

        # Must match basic email pattern
        if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
            return None

        # Must have something before and after @
        parts = email.split('@')
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return None

        local, domain = parts

        # Reject obvious placeholder/example emails
        placeholders = {
            'example.com', 'test.com', 'email.com', 'noreply.com',
            'placeholder.com', 'domain.com', 'yoursite.com',
            'sample.com', 'fake.com', 'test.org',
        }
        if domain in placeholders:
            return None

        # Reject if local part is just 'email', 'user', 'name', etc.
        if local in {'email', 'user', 'name', 'test', 'admin', 'info',
                     'contact', 'hello', 'mail', 'noreply', 'no-reply'}:
            return None

        # Local part must be at least 2 chars
        if len(local) < 2:
            return None

        # Domain must have at least one dot
        if '.' not in domain:
            return None

        return email

    def _validate_city(self, raw: str) -> str | None:
        """
        Returns cleaned city name or None if invalid.
        Rejects: too short, numbers in city name, known non-city words.
        """
        if not raw:
            return None

        city = raw.strip().strip(',').strip()

        # Too short or too long
        if not (2 <= len(city) <= 60):
            return None

        # City names don't contain digits
        if re.search(r'\d', city):
            return None

        # City names shouldn't start with lowercase (unless it's a small word)
        if city[0].islower():
            return None

        # Reject known non-city words
        if city.lower() in self._NOT_A_CITY:
            return None

        # Reject if it's just punctuation or symbols
        if not re.match(r"^[A-Za-z\s\-\.']+$", city):
            return None

        # Reject single-word entries that are just common English words
        # (city names can be single words but they should be proper nouns)
        if ' ' not in city and city.lower() in _INVALID_NAME_WORDS:
            return None

        return city.title()

    def _validate_region(self, raw: str, country: str = None) -> str | None:
        """
        Returns validated region/state/province code or None if invalid.
        Accepts 2-3 letter region codes that exist in our known sets.
        """
        if not raw:
            return None

        region = raw.strip().upper()

        # Must be 2-3 uppercase letters
        if not re.match(r'^[A-Z]{2,3}$', region):
            return None

        # Must be a known valid region code
        if region not in self._ALL_VALID_REGIONS:
            return None

        # If country is specified, verify the region belongs to that country
        if country == 'US' and region not in self.US_STATES:
            return None
        if country == 'CA' and region not in self.CA_PROVINCES:
            return None
        if country == 'AU' and region not in self.AU_STATES:
            return None
        if country == 'GB' and region not in self.UK_REGIONS:
            return None

        return region

    def _validate_postal(self, raw: str, country: str = 'US') -> str | None:
        """
        Returns validated postal/zip code or None if invalid.
        Format varies by country — CA: M5V 1A1, US: 78701, GB: SW1A 2AA, AU: 2000
        """
        if not raw:
            return None

        postal = raw.strip().upper()

        pattern = self._POSTAL_PATTERNS.get(country)
        if pattern and pattern.match(postal):
            return postal

        # If country unknown, accept any reasonable postal format
        if re.match(r'^[A-Z0-9]{3,8}(\s?[A-Z0-9]{0,4})?$', postal):
            return postal

        return None

    def _validate_age(self, raw) -> int | None:
        """
        Returns validated age as integer or None if implausible.
        Accepts ages 5–110 only — rejects zip codes, years, etc.
        """
        if raw is None:
            return None

        try:
            age = int(str(raw).strip())
        except (ValueError, TypeError):
            return None

        # Real human age range
        if not (5 <= age <= 110):
            return None

        return age

    def _validate_url(self, raw: str, base_domain: str = None) -> str | None:
        """
        Returns validated URL or None.
        Optionally checks that the URL belongs to the expected domain.
        """
        if not raw:
            return None

        url = raw.strip()

        # Must start with http(s) or be a relative path
        if not (url.startswith('http://') or url.startswith('https://') or url.startswith('/')):
            return None

        # Reject javascript: and data: URIs
        if url.startswith('javascript:') or url.startswith('data:'):
            return None

        # Reject fragment-only links
        if url.startswith('#'):
            return None

        # If base domain specified, verify URL belongs to it
        if base_domain and url.startswith('http'):
            if base_domain not in url:
                return None

        return url

    def _validate_relative_name(self, raw: str) -> str | None:
        """Validates a relative/associate name using the same name validator."""
        if not raw:
            return None
        name = raw.strip()
        if is_valid_person_name(name):
            full, _, _ = clean_name(name)
            return full
        return None

    def _validate_employer(self, raw: str) -> str | None:
        """
        Validates an employer/company name.
        More permissive than person names — allows numbers and some symbols.
        """
        if not raw:
            return None

        employer = raw.strip()

        # Too short or too long
        if not (2 <= len(employer) <= 150):
            return None

        # Reject known non-employer garbage words
        garbage = {'unknown', 'none', 'null', 'n/a', 'na', 'not available',
                   'undefined', 'employer', 'company', 'workplace', 'job'}
        if employer.lower() in garbage:
            return None

        # Must contain at least one letter
        if not re.search(r'[A-Za-z]', employer):
            return None

        return employer

    def _validate_job_title(self, raw: str) -> str | None:
        """Validates a job title — letters, spaces, hyphens, slashes."""
        if not raw:
            return None

        title = raw.strip()

        if not (2 <= len(title) <= 100):
            return None

        garbage = {'unknown', 'none', 'null', 'n/a', 'na', 'job title',
                   'position', 'occupation', 'role', 'title'}
        if title.lower() in garbage:
            return None

        if not re.search(r'[A-Za-z]', title):
            return None

        return title

    # ══════════════════════════════════════════════════════════════════
    # FIELD PARSERS — now all run through validators
    # ══════════════════════════════════════════════════════════════════

    def _parse_phones_enhanced(self, sel) -> list:
        """Extract and validate phone numbers from a selector."""
        phones  = []
        seen    = set()
        raw_pat = re.compile(r'[\+\(]?[\d][\d\s\-\(\)\.]{6,18}')

        selectors = [
            "[class*='phone']::text",
            "[class*='tel']::text",
            "[class*='telephone']::text",
            "[class*='contact']::text",
            "[class*='number']::text",
            "a[href^='tel:']::attr(href)",
            "span[itemprop='telephone']::text",
            "td[data-label='Phone']::text",
            "li[class*='phone']::text",
        ]

        all_texts = []
        for s in selectors:
            all_texts.extend(sel.css(s).getall())

        for text in all_texts:
            text = text.replace("tel:", "").strip()
            for match in raw_pat.findall(text):
                cleaned = self._validate_phone(match)
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    phones.append({
                        "phone": cleaned,
                        "type":  self._classify_phone(cleaned),
                    })

        return phones

    def _parse_emails_enhanced(self, sel) -> list:
        """Extract and validate email addresses from a selector."""
        pattern = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
        seen    = set()
        emails  = []

        full_text = " ".join(sel.css("::text").getall())
        for match in pattern.findall(full_text):
            cleaned = self._validate_email(match)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                emails.append(cleaned)

        for href in sel.css("a[href^='mailto:']::attr(href)").getall():
            raw     = href.replace("mailto:", "").split("?")[0].strip()
            cleaned = self._validate_email(raw)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                emails.append(cleaned)

        return emails

    def _parse_addresses(self, sel, default_country="US") -> list:
        """Extract and validate address blocks from a selector."""
        addresses = []
        blocks    = sel.css(
            ".address, .location, [class*='address'], [class*='location'], "
            "[class*='city'], [itemprop='address'], td[data-label='Address']"
        )
        for i, block in enumerate(blocks):
            text = " ".join(block.css("::text").getall()).strip()
            if not text:
                continue

            raw_city, raw_region, raw_postal = self._split_location(text)

            # Detect country from region first
            detected_country = self._detect_country(raw_region) if raw_region else default_country

            # Validate each field
            city    = self._validate_city(raw_city)
            region  = self._validate_region(raw_region, detected_country)
            postal  = self._validate_postal(raw_postal, detected_country)
            country = detected_country if region else default_country

            # Only save address if we have at least a valid city or region
            if city or region:
                addresses.append({
                    "address":     "",
                    "city":        city   or "",
                    "state":       region or "",
                    "postal_code": postal or "",
                    "country":     country,
                    "is_current":  i == 0,
                })

        return addresses

    def _parse_phones(self, sel) -> list:
        return self._parse_phones_enhanced(sel)

    def _parse_emails(self, sel) -> list:
        return self._parse_emails_enhanced(sel)

    def _parse_relatives(self, sel) -> list:
        """Extract and validate relative/associate names."""
        relatives = []
        seen      = set()
        for block in sel.css("[class*='relative'], [class*='associate'], [class*='known']"):
            raw  = (block.css("::text").get() or "").strip()
            name = self._validate_relative_name(raw)
            if name and name not in seen:
                seen.add(name)
                relatives.append({"name": name, "relation": "associate"})
        return relatives

    def _parse_employment(self, sel) -> list:
        """Extract and validate employment details."""
        employment = []
        for block in sel.css("[class*='employ'], [class*='work'], [class*='job'], [class*='career']"):
            raw_employer  = (block.css("[class*='company']::text").get() or "").strip()
            raw_job_title = (block.css("[class*='title']::text, [class*='position']::text").get() or "").strip()
            employer  = self._validate_employer(raw_employer)
            job_title = self._validate_job_title(raw_job_title)
            if employer or job_title:
                employment.append({
                    "employer":     employer  or "",
                    "job_title":    job_title or "",
                    "income_range": "",
                })
        return employment

    def _parse_socials(self, sel) -> list:
        """Extract and validate social media profile links."""
        socials = []
        seen    = set()
        for link in sel.css("a::attr(href)").getall():
            if not link:
                continue
            for domain, platform in self._SOCIAL_DOMAINS.items():
                if domain in link:
                    # Validate the URL
                    clean_url = self._validate_url(link)
                    if not clean_url or clean_url in seen:
                        continue
                    seen.add(clean_url)
                    username = clean_url.rstrip("/").split("/")[-1]
                    # Username should look real — not empty or a path segment
                    if username and username not in {'home','feed','profile','people'}:
                        socials.append({
                            "platform":    platform,
                            "profile_url": clean_url,
                            "username":    username,
                        })
        return socials

    # ── Helpers ────────────────────────────────────────────────────────

    def _detect_country(self, region: str) -> str:
        """Detect country from a region/state/province code."""
        r = region.upper().strip() if region else ""
        if r in self.CA_PROVINCES:
            return "CA"
        if r in self.US_STATES:
            return "US"
        if r in self.AU_STATES:
            return "AU"
        if r in self.UK_REGIONS:
            return "GB"
        return self.country

    def _extract_age(self, text: str):
        match = re.search(r'\b(\d{1,3})\b', text)
        if match:
            return self._validate_age(match.group(1))
        return None

    def _split_location(self, text: str):
        """
        Splits a location string into (city, region, postal).
        Handles formats:
          Toronto, ON M5V 1A1
          Austin, TX 78701
          London, ENG
          New South Wales, NSW 2000
        """
        # Try full format: City, REGION POSTAL
        match = re.search(
            r'([A-Za-z][A-Za-z\s\-\.]{1,40}),\s*'
            r'([A-Z]{2,3})'
            r'(?:\s+([A-Z0-9]{3,4}\s?[A-Z0-9]{0,3}|\d{4,6}))?',
            text
        )
        if match:
            city   = match.group(1).strip()
            region = match.group(2).strip()
            postal = (match.group(3) or "").strip()
            return city, region, postal

        return "", "", ""

    def handle_error(self, failure):
        print(f"[Spider] Request failed: {failure.request.url} — {failure.value}")
