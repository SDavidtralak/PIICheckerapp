import time
import socket
import logging
from scrapy import signals

logger = logging.getLogger(__name__)


def check_internet(host="8.8.8.8", port=53, timeout=5) -> bool:
    try:
        socket.setdefaulttimeout(timeout)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        sock.close()
        return True
    except (socket.error, OSError):
        return False


def wait_for_internet(check_interval=15, max_wait=3600):
    elapsed = 0
    print(f"\n[ConnectionMonitor] ⚠ Internet lost — waiting for reconnection...")
    print(f"[ConnectionMonitor] Checking every {check_interval}s (giving up after {max_wait//60} mins)")

    while elapsed < max_wait:
        time.sleep(check_interval)
        elapsed += check_interval
        if check_internet():
            print(f"[ConnectionMonitor] ✓ Internet restored after {elapsed}s — resuming.")
            return True
        mins = elapsed // 60
        secs = elapsed % 60
        print(f"[ConnectionMonitor] Still offline... ({mins}m {secs}s elapsed)")

    print(f"[ConnectionMonitor] ✗ Internet not restored after {max_wait//60} mins — stopping.")
    return False


class ConnectionMonitorMiddleware:
    """
    Detects internet loss, pauses scraping, resumes when back online.
    Updated to use crawler-based instantiation to avoid Scrapy deprecation warnings.
    """

    ERROR_THRESHOLD = 3
    CHECK_INTERVAL  = 15
    MAX_WAIT        = 3600

    def __init__(self, crawler):
        self.crawler           = crawler
        self.consecutive_errors = 0
        self.is_paused          = False
        crawler.signals.connect(self._spider_opened, signal=signals.spider_opened)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def _spider_opened(self, spider):
        logger.info("[ConnectionMonitor] Active — will auto-pause on internet loss.")

    # ── No spider argument — uses self.crawler.spider instead ─────────
    def process_request(self, request):
        if self.is_paused:
            self._block_until_online()
        return None

    def process_response(self, request, response):
        if self.consecutive_errors > 0:
            self.consecutive_errors = 0
        return response

    def process_exception(self, request, exception):
        error_keywords = ['connection', 'timeout', 'dns', 'network', 'refused']
        is_network_error = any(kw in str(exception).lower() for kw in error_keywords)

        if is_network_error:
            self.consecutive_errors += 1
            print(f"[ConnectionMonitor] Network error #{self.consecutive_errors}: {exception}")

            if self.consecutive_errors >= self.ERROR_THRESHOLD:
                if not check_internet():
                    self.is_paused = True
                    restored = wait_for_internet(
                        check_interval=self.CHECK_INTERVAL,
                        max_wait=self.MAX_WAIT
                    )
                    if restored:
                        self.is_paused          = False
                        self.consecutive_errors = 0
                        print(f"[ConnectionMonitor] Retrying: {request.url}")
                        return request
                    else:
                        print(f"[ConnectionMonitor] Stopping spider due to prolonged outage.")
                        spider = getattr(self.crawler, 'spider', None)
                        if spider:
                            self.crawler.engine.close_spider(spider, "internet_outage")
                        return None
                else:
                    self.consecutive_errors = 0

        return None

    def _block_until_online(self):
        while self.is_paused:
            if check_internet():
                self.is_paused          = False
                self.consecutive_errors = 0
                print(f"[ConnectionMonitor] ✓ Back online — resuming.")
                return
            time.sleep(self.CHECK_INTERVAL)