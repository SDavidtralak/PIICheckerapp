import mysql.connector
from mysql.connector import pooling
from datetime import datetime


class MySQLPipeline:
    """
    High-speed pipeline with:
    - Connection pooling
    - Batch commits every 50 records
    - SAFE mark-and-sweep with three protections against data loss:

      PROTECTION 1 — Minimum confirmation threshold:
        The sweep deletion only runs if at least MIN_CONFIRMED_TO_SWEEP
        records were re-confirmed during this run. If the spider got
        blocked and confirmed 0 records, nothing gets deleted.

      PROTECTION 2 — Percentage guard:
        The sweep only deletes stale records if the number of records
        to be deleted is less than MAX_DELETE_PERCENT of existing records.
        If >50% would be deleted, the sweep is skipped — this indicates
        the broker was blocking requests, not that the records are stale.

      PROTECTION 3 — Delayed mark phase:
        Records are only marked inactive AFTER the spider confirms it
        can actually reach and scrape the site (first successful item).
        If the spider gets blocked immediately, nothing is ever marked.
    """

    BATCH_SIZE             = 50
    MIN_CONFIRMED_TO_SWEEP = 100   # must confirm at least 100 records before deleting anything
    MAX_DELETE_PERCENT     = 50    # never delete more than 50% of existing records in one run
    _pool                  = None

    def __init__(self, crawler):
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    @classmethod
    def _get_pool(cls):
        if cls._pool is None:
            cls._pool = pooling.MySQLConnectionPool(
                pool_name          = "checkpii_pool",
                pool_size          = 3,
                pool_reset_session = True,
                host               = "localhost",
                database           = "checkpii",
                user               = "root",
                password           = "evoplan12",   # ← change this
                autocommit         = False,
                charset            = "utf8mb4",
            )
        return cls._pool

    def open_spider(self, spider):
        self.pool              = self._get_pool()
        self.conn              = self.pool.get_connection()
        self.cursor            = self.conn.cursor()
        self.records_scraped   = 0
        self.records_removed   = 0
        self.batch_count       = 0
        self.scrape_start      = datetime.now()
        self.mark_done         = False   # PROTECTION 3 — tracks if mark phase ran
        self.broker_id         = spider.broker_id

        # How many records exist for this broker before the run starts
        self.cursor.execute(
            "SELECT COUNT(*) FROM people WHERE broker_id = %s AND is_active = TRUE",
            (self.broker_id,)
        )
        self.existing_count = self.cursor.fetchone()[0]

        # Create scrape job
        self.cursor.execute("""
            INSERT INTO scrape_jobs (broker_id, status, started_at)
            VALUES (%s, 'running', NOW())
        """, (self.broker_id,))
        self.conn.commit()
        self.scrape_job_id = self.cursor.lastrowid

        print(f"[Pipeline] Scrape job {self.scrape_job_id} started.")
        print(f"[Pipeline] Broker {self.broker_id} has {self.existing_count} existing records.")
        print(f"[Pipeline] Mark phase deferred — will run after first successful scrape.")

    def _run_mark_phase(self):
        """
        PROTECTION 3 — Only called after the first item is successfully scraped.
        If the spider never reaches a site, this never runs and nothing is marked.
        """
        if self.mark_done:
            return
        self.cursor.execute("""
            UPDATE people SET is_active = FALSE WHERE broker_id = %s
        """, (self.broker_id,))
        self.conn.commit()
        marked = self.cursor.rowcount
        print(f"[Pipeline] Mark phase complete — {marked} records flagged for review.")
        self.mark_done = True

    def process_item(self, item, spider):
        try:
            broker_id = item.get('broker_id')
            full_name = (item.get('full_name') or '').strip()
            if not full_name:
                return item

            # PROTECTION 3 — run mark phase on first successful item only
            self._run_mark_phase()

            # Check if person already exists
            self.cursor.execute("""
                SELECT id FROM people
                WHERE broker_id = %s AND full_name = %s
                LIMIT 1
            """, (broker_id, full_name))
            existing = self.cursor.fetchone()

            if existing:
                person_id = existing[0]
                self.cursor.execute("""
                    UPDATE people
                    SET is_active = TRUE, last_confirmed = NOW(),
                        age = %s, listing_url = %s
                    WHERE id = %s
                """, (item.get('age'), item.get('listing_url'), person_id))
                for tbl in ['addresses','phone_numbers','email_addresses',
                             'relatives','employment','social_profiles']:
                    self.cursor.execute(
                        f"DELETE FROM {tbl} WHERE person_id = %s", (person_id,)
                    )
            else:
                self.cursor.execute("""
                    INSERT INTO people
                        (broker_id, full_name, first_name, last_name,
                         age, listing_url, is_active, first_seen, last_confirmed)
                    VALUES (%s,%s,%s,%s,%s,%s,TRUE,NOW(),NOW())
                """, (
                    broker_id,
                    full_name,
                    item.get('first_name', ''),
                    item.get('last_name', ''),
                    item.get('age'),
                    item.get('listing_url', ''),
                ))
                person_id = self.cursor.lastrowid

            # Insert child records
            if item.get('addresses'):
                self.cursor.executemany("""
                    INSERT INTO addresses
                        (person_id, address, city, state, postal_code, country, is_current)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, [
                    (person_id,
                     a.get('address',''), a.get('city',''), a.get('state',''),
                     a.get('postal_code',''), a.get('country','US'), a.get('is_current',True))
                    for a in item['addresses']
                ])

            if item.get('phone_numbers'):
                self.cursor.executemany("""
                    INSERT INTO phone_numbers (person_id, phone, type)
                    VALUES (%s,%s,%s)
                """, [
                    (person_id, p.get('phone',''), p.get('type','unknown'))
                    for p in item['phone_numbers']
                ])

            if item.get('email_addresses'):
                self.cursor.executemany("""
                    INSERT INTO email_addresses (person_id, email)
                    VALUES (%s,%s)
                """, [(person_id, e) for e in item['email_addresses']])

            if item.get('relatives'):
                self.cursor.executemany("""
                    INSERT INTO relatives (person_id, name, relation)
                    VALUES (%s,%s,%s)
                """, [
                    (person_id, r.get('name',''), r.get('relation','unknown'))
                    for r in item['relatives']
                ])

            if item.get('employment'):
                self.cursor.executemany("""
                    INSERT INTO employment
                        (person_id, employer, job_title, income_range)
                    VALUES (%s,%s,%s,%s)
                """, [
                    (person_id, e.get('employer',''), e.get('job_title',''), e.get('income_range',''))
                    for e in item['employment']
                ])

            if item.get('social_profiles'):
                self.cursor.executemany("""
                    INSERT INTO social_profiles
                        (person_id, platform, profile_url, username)
                    VALUES (%s,%s,%s,%s)
                """, [
                    (person_id, s.get('platform',''), s.get('profile_url',''), s.get('username',''))
                    for s in item['social_profiles']
                ])

            self.records_scraped += 1
            self.batch_count     += 1

            if self.batch_count >= self.BATCH_SIZE:
                self.conn.commit()
                self.batch_count = 0
                print(f"[Pipeline] {self.records_scraped} records saved...")

        except Exception as e:
            self.conn.rollback()
            self.batch_count = 0
            print(f"[Pipeline] ERROR '{item.get('full_name')}': {e}")

        return item

    def close_spider(self, spider):
        # Final commit of any remaining batch
        self.conn.commit()

        # ── SAFE SWEEP ────────────────────────────────────────────────────
        if not self.mark_done:
            # PROTECTION 3 triggered — mark phase never ran, meaning the spider
            # never successfully scraped a single record. Nothing was marked
            # inactive so there is nothing to delete. Database is untouched.
            print(f"[Pipeline] ⚠ SWEEP SKIPPED — spider never confirmed any records.")
            print(f"[Pipeline] ⚠ Site was likely blocked. Existing {self.existing_count} records preserved.")
            self._fail_job("Spider never reached site — possible network block")

        elif self.records_scraped < self.MIN_CONFIRMED_TO_SWEEP:
            # PROTECTION 1 triggered — spider ran but collected too few records
            # to safely delete anything. Restore all marked records.
            print(f"[Pipeline] ⚠ SWEEP SKIPPED — only {self.records_scraped} records confirmed "
                  f"(minimum {self.MIN_CONFIRMED_TO_SWEEP} required).")
            print(f"[Pipeline] ⚠ Restoring all marked records to protect against data loss.")
            self.cursor.execute("""
                UPDATE people SET is_active = TRUE WHERE broker_id = %s AND is_active = FALSE
            """, (self.broker_id,))
            self.conn.commit()
            restored = self.cursor.rowcount
            print(f"[Pipeline] ✓ {restored} records restored.")
            self._fail_job(f"Too few records confirmed ({self.records_scraped}) — sweep aborted")

        else:
            # Count how many would be deleted before actually deleting
            self.cursor.execute("""
                SELECT COUNT(*) FROM people
                WHERE broker_id = %s AND is_active = FALSE
            """, (self.broker_id,))
            stale_count = self.cursor.fetchone()[0]

            # PROTECTION 2 — percentage guard
            if self.existing_count > 0:
                delete_pct = (stale_count / self.existing_count) * 100
            else:
                delete_pct = 0

            if delete_pct > self.MAX_DELETE_PERCENT:
                # Too many records would be deleted — site was likely partially blocked
                print(f"[Pipeline] ⚠ SWEEP SKIPPED — would delete {stale_count} records "
                      f"({delete_pct:.1f}% of existing). Threshold is {self.MAX_DELETE_PERCENT}%.")
                print(f"[Pipeline] ⚠ Restoring marked records to protect against data loss.")
                self.cursor.execute("""
                    UPDATE people SET is_active = TRUE WHERE broker_id = %s AND is_active = FALSE
                """, (self.broker_id,))
                self.conn.commit()
                restored = self.cursor.rowcount
                print(f"[Pipeline] ✓ {restored} records restored. Run again on a reliable connection.")
                self._fail_job(f"Sweep would delete {delete_pct:.1f}% of records — aborted for safety")

            else:
                # All protections passed — safe to sweep
                self.cursor.execute("""
                    DELETE FROM people WHERE broker_id = %s AND is_active = FALSE
                """, (self.broker_id,))
                self.records_removed = self.cursor.rowcount
                self.conn.commit()
                print(f"[Pipeline] ✓ Sweep complete — removed {self.records_removed} stale records "
                      f"({delete_pct:.1f}% of previous total).")
                self._complete_job()

        # Update broker last_scraped timestamp
        self.cursor.execute(
            "UPDATE brokers SET last_scraped = NOW() WHERE id = %s",
            (self.broker_id,)
        )
        self.conn.commit()
        self.cursor.close()
        self.conn.close()

        duration = (datetime.now() - self.scrape_start).seconds
        mins     = duration // 60
        secs     = duration % 60
        rate     = round(self.records_scraped / max(duration, 1), 1)
        print(f"[Pipeline] Done in {mins}m {secs}s — "
              f"{self.records_scraped} saved, {self.records_removed} removed, "
              f"{rate} records/sec.")

    def _complete_job(self):
        self.cursor.execute("""
            UPDATE scrape_jobs
            SET status='completed', completed_at=NOW(),
                records_scraped=%s, records_removed=%s
            WHERE id=%s
        """, (self.records_scraped, self.records_removed, self.scrape_job_id))
        self.conn.commit()

    def _fail_job(self, reason):
        self.cursor.execute("""
            UPDATE scrape_jobs
            SET status='failed', completed_at=NOW(),
                records_scraped=%s, records_removed=0,
                error_message=%s
            WHERE id=%s
        """, (self.records_scraped, reason, self.scrape_job_id))
        self.conn.commit()