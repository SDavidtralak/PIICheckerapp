"""
CheckPII — Rotating Proxy Middleware
=====================================
Automatically rotates through proxy IPs on every request to avoid
IP-based blocking. Supports three modes:

  MODE 1 — Free proxies (default)
    Fetches fresh proxies from public lists automatically.
    Unreliable (~30% work) but costs nothing.

  MODE 2 — Your own proxy list
    Add IPs to PROXY_LIST below. Useful if you have access to
    a VPN that exposes proxy endpoints.

  MODE 3 — ScraperAPI ($30/month)
    Set SCRAPERAPI_KEY below. Handles Cloudflare, CAPTCHA,
    and IP rotation automatically. Most reliable option.

To switch modes, set PROXY_MODE in settings.py:
    PROXY_MODE = 'free'        # Mode 1
    PROXY_MODE = 'list'        # Mode 2
    PROXY_MODE = 'scraperapi'  # Mode 3
    PROXY_MODE = 'off'         # Disabled (use your own IP/VPN)
"""

import random
import logging
import threading
import time
import urllib.request
from scrapy import signals
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# CONFIGURATION — edit these values
# ══════════════════════════════════════════════════════════════════════

# ScraperAPI key — get one free at https://www.scraperapi.com
# Free tier: 1,000 requests/month. Paid: $30/mo = 1M requests
SCRAPERAPI_KEY = ""   # ← paste your key here when you subscribe

# Your own proxy list — format: "http://ip:port" or "http://user:pass@ip:port"
# Leave empty to use free proxies instead
PROXY_LIST = [
    # "http://123.456.789.0:8080",
    # "http://user:pass@proxy.example.com:3128",
]

# Free proxy sources — fetched fresh at spider start
FREE_PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
]

# How many free proxies to load (more = more variety, slower startup)
MAX_FREE_PROXIES = 100

# How many failures before a proxy is removed from rotation
MAX_PROXY_FAILURES = 3

# Refresh free proxy list every N minutes
PROXY_REFRESH_MINUTES = 30

# ══════════════════════════════════════════════════════════════════════


class ProxyRotatorMiddleware:
    """
    Scrapy downloader middleware that rotates proxy IPs on every request.
    Tracks failures and removes bad proxies automatically.
    """

    def __init__(self, mode, scraperapi_key):
        self.mode           = mode
        self.scraperapi_key = scraperapi_key
        self.proxies        = []
        self.failures       = {}   # proxy -> failure count
        self.lock           = threading.Lock()
        self.last_refresh   = 0

        if mode == 'off':
            logger.info("[ProxyRotator] Disabled — using direct connection.")
        elif mode == 'scraperapi':
            if not scraperapi_key:
                logger.warning("[ProxyRotator] ScraperAPI mode but no key set. "
                               "Add your key to SCRAPERAPI_KEY in proxy_rotator.py")
            else:
                logger.info("[ProxyRotator] ScraperAPI mode active.")
        elif mode == 'list':
            self.proxies = list(PROXY_LIST)
            logger.info(f"[ProxyRotator] List mode — {len(self.proxies)} proxies loaded.")
        elif mode == 'free':
            self._refresh_free_proxies()
            logger.info(f"[ProxyRotator] Free proxy mode — {len(self.proxies)} proxies loaded.")

    @classmethod
    def from_crawler(cls, crawler):
        mode = crawler.settings.get('PROXY_MODE', 'off')
        if mode == 'off':
            raise NotConfigured("Proxy rotation disabled (PROXY_MODE = 'off')")
        return cls(mode=mode, scraperapi_key=SCRAPERAPI_KEY)

    def _refresh_free_proxies(self):
        """Fetch fresh proxy list from public sources."""
        now = time.time()
        if now - self.last_refresh < PROXY_REFRESH_MINUTES * 60:
            return  # not time yet

        fresh = []
        for url in FREE_PROXY_SOURCES:
            try:
                req  = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                resp = urllib.request.urlopen(req, timeout=10)
                lines = resp.read().decode('utf-8').strip().splitlines()
                for line in lines:
                    line = line.strip()
                    if line and ':' in line and not line.startswith('#'):
                        proxy = f"http://{line}" if not line.startswith('http') else line
                        fresh.append(proxy)
                        if len(fresh) >= MAX_FREE_PROXIES:
                            break
            except Exception as e:
                logger.debug(f"[ProxyRotator] Failed to fetch from {url}: {e}")

            if len(fresh) >= MAX_FREE_PROXIES:
                break

        if fresh:
            with self.lock:
                self.proxies    = fresh[:MAX_FREE_PROXIES]
                self.failures   = {}
                self.last_refresh = now
            logger.info(f"[ProxyRotator] Refreshed — {len(self.proxies)} free proxies available.")
        else:
            logger.warning("[ProxyRotator] Could not fetch any free proxies. "
                           "Check your internet connection.")

    def _get_proxy(self):
        """Pick a random working proxy from the pool."""
        with self.lock:
            working = [p for p in self.proxies
                       if self.failures.get(p, 0) < MAX_PROXY_FAILURES]
        if not working:
            logger.warning("[ProxyRotator] All proxies exhausted — "
                           "refreshing list.")
            self._refresh_free_proxies()
            with self.lock:
                working = list(self.proxies)
        return random.choice(working) if working else None

    def _mark_failure(self, proxy):
        """Record a proxy failure. Remove it if it exceeds the threshold."""
        with self.lock:
            self.failures[proxy] = self.failures.get(proxy, 0) + 1
            if self.failures[proxy] >= MAX_PROXY_FAILURES:
                if proxy in self.proxies:
                    self.proxies.remove(proxy)
                logger.debug(f"[ProxyRotator] Removed bad proxy: {proxy} "
                             f"(failed {MAX_PROXY_FAILURES} times)")

    def _scraperapi_url(self, url):
        """Wrap a URL with the ScraperAPI endpoint."""
        import urllib.parse
        encoded = urllib.parse.quote(url)
        return (f"https://api.scraperapi.com/?api_key={self.scraperapi_key}"
                f"&url={encoded}&render=true&country_code=us")

    def process_request(self, request, spider):
        if self.mode == 'off':
            return

        # Refresh free proxies periodically
        if self.mode == 'free':
            self._refresh_free_proxies()

        if self.mode == 'scraperapi' and self.scraperapi_key:
            # Rewrite URL to go through ScraperAPI
            # Skip if already routed through ScraperAPI
            if 'scraperapi.com' not in request.url:
                request = request.replace(url=self._scraperapi_url(request.url))
            return request

        elif self.mode in ('free', 'list'):
            proxy = self._get_proxy()
            if proxy:
                request.meta['proxy'] = proxy
                request.meta['_proxy_used'] = proxy
                logger.debug(f"[ProxyRotator] Using proxy: {proxy}")

    def process_response(self, request, response, spider):
        # Mark proxy as failed if we got a block response
        proxy = request.meta.get('_proxy_used')
        if proxy and response.status in (403, 407, 429, 503):
            logger.debug(f"[ProxyRotator] Proxy blocked ({response.status}): {proxy}")
            self._mark_failure(proxy)
        return response

    def process_exception(self, request, exception, spider):
        # Mark proxy as failed on connection errors
        proxy = request.meta.get('_proxy_used')
        if proxy:
            logger.debug(f"[ProxyRotator] Proxy error ({type(exception).__name__}): {proxy}")
            self._mark_failure(proxy)
        return None
