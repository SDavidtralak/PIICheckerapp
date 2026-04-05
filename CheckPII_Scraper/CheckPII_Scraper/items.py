import scrapy


class PersonItem(scrapy.Item):
    # ── Broker info ────────────────────────────────────────────────────
    broker_id       = scrapy.Field()
    broker_name     = scrapy.Field()
    broker_url      = scrapy.Field()
    listing_url     = scrapy.Field()

    # ── Core identity ──────────────────────────────────────────────────
    full_name       = scrapy.Field()
    first_name      = scrapy.Field()
    last_name       = scrapy.Field()
    age             = scrapy.Field()

    # ── Addresses (list of dicts) ──────────────────────────────────────
    # [{ address, city, state, postal_code, is_current }]
    addresses       = scrapy.Field()

    # ── Phone numbers (list of dicts) ─────────────────────────────────
    # [{ phone, type }]
    phone_numbers   = scrapy.Field()

    # ── Email addresses (list of strings) ─────────────────────────────
    email_addresses = scrapy.Field()

    # ── Relatives (list of dicts) ──────────────────────────────────────
    # [{ name, relation }]
    relatives       = scrapy.Field()

    # ── Employment (list of dicts) ─────────────────────────────────────
    # [{ employer, job_title, income_range }]
    employment      = scrapy.Field()

    # ── Social profiles (list of dicts) ───────────────────────────────
    # [{ platform, profile_url, username }]
    social_profiles = scrapy.Field()