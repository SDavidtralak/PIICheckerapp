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
# PLAYWRIGHT — Real Chromium browser for JS rendering + bot bypass
# Install: pip install scrapy-playwright && playwright install chromium
# ══════════════════════════════════════════════════════════════════════

DOWNLOAD_HANDLERS = {
    "http":  "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

PLAYWRIGHT_BROWSER_TYPE = "chromium"

PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--window-size=1920,1080",

        # ── Anti-detection — remove all automation signatures ───────
        "--disable-blink-features=AutomationControlled",
        "--disable-automation",
        "--exclude-switches=enable-automation",
        "--disable-infobars",

        # ── Stealth — make browser behave like real Chrome ──────────
        "--enable-features=NetworkService,NetworkServiceInProcess",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-web-security",
        "--allow-running-insecure-content",

        # ── Memory management — prevents the OOM crash ──────────────
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

# Per-page context — configured to match a real Chrome user
PLAYWRIGHT_CONTEXTS = {
    "default": {
        "viewport":            {"width": 1920, "height": 1080},
        "locale":              "en-US",
        "timezone_id":         "America/New_York",
        "ignore_https_errors": True,
        "java_script_enabled": True,
        # Realistic user agent — matches a real Chrome 120 on Windows
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        # Extra HTTP headers that real browsers always send
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

# Block heavy resources to reduce memory usage and speed up scraping
PLAYWRIGHT_ABORT_REQUEST = lambda req: req.resource_type in {
    "image", "media", "font", "stylesheet", "websocket", "eventsource"
}

# ── Reduced from 4 to 2 — fewer concurrent pages = less memory usage ──
PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 2

# Required — Playwright needs asyncio reactor
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# ══════════════════════════════════════════════════════════════════════
# SPEED SETTINGS — balanced for memory safety
# ══════════════════════════════════════════════════════════════════════

# Reduced from 8 to 4 — prevents too many browser pages at once
CONCURRENT_REQUESTS            = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2

DOWNLOAD_DELAY   = 1
DOWNLOAD_TIMEOUT = 60

AUTOTHROTTLE_ENABLED            = True
AUTOTHROTTLE_START_DELAY        = 1
AUTOTHROTTLE_MAX_DELAY          = 15
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.5

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
warnings.filterwarnings('ignore', message='.*RandomUserAgentMiddleware.*spider argument.*')

# ── Fingerprint ────────────────────────────────────────────────────────
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
