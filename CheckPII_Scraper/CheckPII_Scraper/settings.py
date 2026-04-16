# ── Project ────────────────────────────────────────────────────────────
BOT_NAME         = "CheckPII_Scraper"
SPIDER_MODULES   = ["CheckPII_Scraper.spiders"]
NEWSPIDER_MODULE = "CheckPII_Scraper.spiders"

# ── Pipeline ───────────────────────────────────────────────────────────
ITEM_PIPELINES = {
    "CheckPII_Scraper.pipelines.MySQLPipeline": 300,
}

# ── Job persistence (resume after stop) ────────────────────────────────
# Pass on command line: -s JOBDIR=crawls/spokeo-1
# JOBDIR = 'crawls/spokeo-1'

# ══════════════════════════════════════════════════════════════════════
# PROXY ROTATION
# ══════════════════════════════════════════════════════════════════════
# Switch modes here:
#   'off'        — use your own IP or VPN (default)
#   'free'       — rotate through free public proxies (unreliable ~30%)
#   'list'       — use your own proxy list (edit proxy_rotator.py)
#   'scraperapi' — use ScraperAPI ($30/mo, most reliable)
#
# If you're using ProtonVPN or another VPN app, keep this 'off' —
# the VPN handles IP rotation at the OS level so the spider
# automatically uses the VPN IP without any extra config.
# ══════════════════════════════════════════════════════════════════════
PROXY_MODE = 'off'

# ══════════════════════════════════════════════════════════════════════
# HANDLER MODE
# ══════════════════════════════════════════════════════════════════════
# Controls which download handler the spider uses per broker type.
#
# HANDLER_MODE = 'impersonate'
#   Uses scrapy-impersonate (curl-cffi) for non-JS brokers.
#   Fixes TLS fingerprint — looks like real Chrome at the network level.
#   Best for: ZabaSearch, AnyWho, Canada411, 411.ca, 192.com, PeekYou
#   Install: pip install scrapy-impersonate
#
# HANDLER_MODE = 'playwright'
#   Uses Playwright (Chromium) for JS-heavy brokers.
#   Required for: Spokeo, TruePeopleSearch, FastPeopleSearch, ThatsThem
#
# The spider automatically picks the right handler per broker —
# you don't need to change anything else.
# ══════════════════════════════════════════════════════════════════════
# ── Download handlers — supports BOTH impersonate and playwright ───────
# scrapy-impersonate handles non-JS requests with a real Chrome TLS
# fingerprint. Playwright handles JS-heavy requests that need a browser.
# The spider picks the right one automatically per broker type.
# If scrapy-impersonate is not installed, falls back to Playwright only.
# ── Download handlers ─────────────────────────────────────────────────
# Playwright is the ONLY registered Scrapy download handler.
# For non-JS brokers, curl-cffi is called DIRECTLY inside the spider
# (not through Scrapy's handler system) which avoids any handler
# conflicts. The response HTML is then fed back into the Scrapy pipeline.
# This is the most reliable approach across all Scrapy versions.
DOWNLOAD_HANDLERS = {
    "http":  "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

IMPERSONATE_BROWSER  = "chrome120"   # Step 1 — Chrome 120 TLS fingerprint

# ── Playwright handler (Step 2 — JS-heavy sites) ──────────────────────
PLAYWRIGHT_BROWSER_TYPE = "chromium"

PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--window-size=1920,1080",
        "--disable-blink-features=AutomationControlled",
        "--disable-automation",
        "--exclude-switches=enable-automation",
        "--disable-infobars",
        "--enable-features=NetworkService,NetworkServiceInProcess",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-web-security",
        "--allow-running-insecure-content",
        "--js-flags=--max-old-space-size=512",
        "--disable-application-cache",
        "--disable-cache",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-translate",
        "--disable-default-apps",
        "--renderer-process-limit=2",
    ],
}

PLAYWRIGHT_CONTEXTS = {
    "default": {
        "viewport":            {"width": 1920, "height": 1080},
        "locale":              "en-US",
        "timezone_id":         "America/New_York",
        "ignore_https_errors": True,
        "java_script_enabled": True,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "extra_http_headers": {
            "Accept-Language":           "en-US,en;q=0.9",
            "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Encoding":           "gzip, deflate, br",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest":            "document",
            "Sec-Fetch-Mode":            "navigate",
            "Sec-Fetch-Site":            "none",
            "Sec-Fetch-User":            "?1",
            "sec-ch-ua":                 '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile":          "?0",
            "sec-ch-ua-platform":        '"Windows"',
        },
    },
}

PLAYWRIGHT_ABORT_REQUEST = lambda req: req.resource_type in {
    "image", "media", "font", "stylesheet", "websocket", "eventsource"
}

PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 2
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# ══════════════════════════════════════════════════════════════════════
# SPEED SETTINGS — Step 3: Slow down to avoid behavioral detection
# ══════════════════════════════════════════════════════════════════════
# Real users don't fire 100 requests per minute. Cloudflare's behavioral
# scoring flags anything that looks machine-speed. These settings make
# the spider look like a slow human reader.
# ══════════════════════════════════════════════════════════════════════

CONCURRENT_REQUESTS            = 1    # One request at a time — like a real user
CONCURRENT_REQUESTS_PER_DOMAIN = 1

# Step 3 — 30 second base delay with randomization (15-45s actual range)
# Real users spend 20-60 seconds reading a page before clicking next
DOWNLOAD_DELAY            = 30
RANDOMIZE_DOWNLOAD_DELAY  = True   # Scrapy multiplies delay by 0.5-1.5x randomly
DOWNLOAD_TIMEOUT          = 90

# AutoThrottle backs off further if the site is slow or returning errors
AUTOTHROTTLE_ENABLED            = True
AUTOTHROTTLE_START_DELAY        = 20
AUTOTHROTTLE_MAX_DELAY          = 90
AUTOTHROTTLE_TARGET_CONCURRENCY = 0.5  # Aim for less than 1 req/sec

DNSCACHE_ENABLED           = True
DNSCACHE_SIZE              = 5000
COMPRESSION_ENABLED        = True
REACTOR_THREADPOOL_MAXSIZE = 10

# ══════════════════════════════════════════════════════════════════════
# MIDDLEWARES
# ══════════════════════════════════════════════════════════════════════
DOWNLOADER_MIDDLEWARES = {
    # ── Proxy rotation — controls which IP requests come from ──────────
    # Change PROXY_MODE above to switch between off/free/list/scraperapi
    'CheckPII_Scraper.proxy_rotator.ProxyRotatorMiddleware': 30,

    'CheckPII_Scraper.connection_monitor.ConnectionMonitorMiddleware': 50,
    'scrapy.downloadermiddlewares.robotstxt.RobotsTxtMiddleware':      100,
    'scrapy.downloadermiddlewares.httpauth.HttpAuthMiddleware':         300,
    'scrapy.downloadermiddlewares.downloadtimeout.DownloadTimeoutMiddleware': 350,
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware':       None,
    'scrapy_user_agents.middlewares.RandomUserAgentMiddleware':         400,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware':               550,
    'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 590,
    'scrapy.downloadermiddlewares.redirect.RedirectMiddleware':         600,
    'scrapy.downloadermiddlewares.cookies.CookiesMiddleware':           700,
    'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware':       750,
    'scrapy.downloadermiddlewares.stats.DownloaderStats':               850,
    'scrapy.downloadermiddlewares.offsite.OffsiteMiddleware':           None,
}

# ── Connection monitor tuning ──────────────────────────────────────────
CONNECTION_MONITOR_ERROR_THRESHOLD = 3
CONNECTION_MONITOR_CHECK_INTERVAL  = 15
CONNECTION_MONITOR_MAX_WAIT        = 3600

# ── Retry ──────────────────────────────────────────────────────────────
RETRY_ENABLED    = True
RETRY_TIMES      = 2
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]

# ── Robots ─────────────────────────────────────────────────────────────
ROBOTSTXT_OBEY = False

# ── Cache ──────────────────────────────────────────────────────────────
HTTPCACHE_ENABLED = False

# ── Logging ────────────────────────────────────────────────────────────
LOG_LEVEL            = "WARNING"
FEED_EXPORT_ENCODING = "utf-8"

import logging
import warnings
logging.getLogger('scrapy_user_agents.user_agent_picker').setLevel(logging.ERROR)
logging.getLogger('scrapy_playwright').setLevel(logging.WARNING)
# Suppress deprecation warnings from third-party libraries we can't control
warnings.filterwarnings('ignore', message='.*RandomUserAgentMiddleware.*spider argument.*')
warnings.filterwarnings('ignore', message='.*ImpersonateDownloadHandler.*coroutine.*')
warnings.filterwarnings('ignore', message='.*download_request is not a coroutine.*')
warnings.filterwarnings('ignore', message='.*start_requests.*deprecated.*')

# ── Fingerprint ────────────────────────────────────────────────────────
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
