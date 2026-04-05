-- ============================================================
-- CheckPII — Data Broker Schema (US + Canada + Global)
-- ============================================================
CREATE TABLE brokers (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    website_url VARCHAR(500) NOT NULL UNIQUE,
    opt_out_url VARCHAR(500),
    category ENUM(
        'people_search',
        'marketing',
        'credit_reporting',
        'background_check',
        'social_aggregator',
        'other'
    ) DEFAULT 'people_search',
    country ENUM('US', 'CA', 'GB', 'AU', 'GLOBAL') DEFAULT 'US',
    is_active BOOLEAN DEFAULT TRUE,
    last_scraped TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- ── US Brokers ─────────────────────────────────────────────────────────
INSERT INTO brokers (
        name,
        website_url,
        opt_out_url,
        category,
        country
    )
VALUES (
        'Spokeo',
        'https://www.spokeo.com',
        'https://www.spokeo.com/optout',
        'people_search',
        'US'
    ),
    (
        'Whitepages',
        'https://www.whitepages.com',
        'https://www.whitepages.com/suppression-requests',
        'people_search',
        'US'
    ),
    (
        'BeenVerified',
        'https://www.beenverified.com',
        'https://www.beenverified.com/app/optout',
        'background_check',
        'US'
    ),
    (
        'PeopleFinder',
        'https://www.peoplefinders.com',
        'https://www.peoplefinders.com/opt-out',
        'people_search',
        'US'
    ),
    (
        'MyLife',
        'https://www.mylife.com',
        'https://www.mylife.com/ccpa/index.pubview',
        'people_search',
        'US'
    ),
    (
        'Intelius',
        'https://www.intelius.com',
        'https://www.intelius.com/opt-out',
        'background_check',
        'US'
    ),
    (
        'Radaris US',
        'https://radaris.com',
        'https://radaris.com/control/privacy',
        'people_search',
        'US'
    ),
    (
        'TruthFinder',
        'https://www.truthfinder.com',
        'https://www.truthfinder.com/opt-out/',
        'background_check',
        'US'
    ),
    (
        'Instantcheckmate',
        'https://www.instantcheckmate.com',
        'https://www.instantcheckmate.com/opt-out/',
        'background_check',
        'US'
    ),
    (
        'USPhoneBook',
        'https://www.usphonebook.com',
        NULL,
        'people_search',
        'US'
    );
-- ── Canadian Brokers ───────────────────────────────────────────────────
INSERT INTO brokers (
        name,
        website_url,
        opt_out_url,
        category,
        country
    )
VALUES (
        'Canada411',
        'https://www.canada411.ca',
        'https://www.canada411.ca/search/rr.html',
        'people_search',
        'CA'
    ),
    (
        'Radaris Canada',
        'https://ca.radaris.com',
        'https://ca.radaris.com/control/privacy',
        'people_search',
        'CA'
    ),
    (
        'Whitepages CA',
        'https://www.whitepages.ca',
        NULL,
        'people_search',
        'CA'
    ),
    (
        '411.ca',
        'https://www.411.ca',
        NULL,
        'people_search',
        'CA'
    ),
    (
        'CanadaPages',
        'https://www.canadapages.com',
        NULL,
        'people_search',
        'CA'
    );
-- ── UK Brokers ─────────────────────────────────────────────────────────
INSERT INTO brokers (
        name,
        website_url,
        opt_out_url,
        category,
        country
    )
VALUES (
        'BT Phone Book',
        'https://www.thephonebook.bt.com',
        NULL,
        'people_search',
        'GB'
    ),
    (
        '192.com',
        'https://www.192.com',
        'https://www.192.com/remove/',
        'people_search',
        'GB'
    ),
    (
        'FindMyPast UK',
        'https://www.findmypast.co.uk',
        NULL,
        'people_search',
        'GB'
    ),
    (
        'UK Electoral Roll',
        'https://www.electoralrolluk.com',
        NULL,
        'people_search',
        'GB'
    );
-- ── Australian Brokers ────────────────────────────────────────────────
INSERT INTO brokers (
        name,
        website_url,
        opt_out_url,
        category,
        country
    )
VALUES (
        'White Pages AU',
        'https://www.whitepages.com.au',
        NULL,
        'people_search',
        'AU'
    ),
    (
        'True People AU',
        'https://www.truepeoplesearch.com.au',
        NULL,
        'people_search',
        'AU'
    );
-- ── Global Brokers ────────────────────────────────────────────────────
INSERT INTO brokers (
        name,
        website_url,
        opt_out_url,
        category,
        country
    )
VALUES (
        'Pipl',
        'https://pipl.com',
        'https://pipl.com/personal-information-removal-policy',
        'people_search',
        'GLOBAL'
    );
-- ── New Tier-1 Brokers — JSON-LD structured data, no paywall ──────────
INSERT INTO brokers (
        name,
        website_url,
        opt_out_url,
        category,
        country
    )
VALUES (
        'TruePeopleSearch',
        'https://www.truepeoplesearch.com',
        'https://www.truepeoplesearch.com/removal',
        'people_search',
        'US'
    ),
    (
        'FastPeopleSearch',
        'https://www.fastpeoplesearch.com',
        'https://www.fastpeoplesearch.com/removal',
        'people_search',
        'US'
    ),
    (
        'ZabaSearch',
        'https://www.zabasearch.com',
        'https://www.zabasearch.com/privacy.php',
        'people_search',
        'US'
    ),
    (
        'ThatsThem',
        'https://thatsthem.com',
        'https://thatsthem.com/optout',
        'people_search',
        'US'
    ),
    (
        'FamilyTreeNow',
        'https://www.familytreenow.com',
        'https://www.familytreenow.com/optout',
        'people_search',
        'US'
    ),
    (
        'AnyWho',
        'https://www.anywho.com',
        NULL,
        'people_search',
        'US'
    ),
    (
        'PeekYou',
        'https://www.peekyou.com',
        'https://www.peekyou.com/about/contact/optout/',
        'people_search',
        'US'
    );
-- ── People table ───────────────────────────────────────────────────────
CREATE TABLE people (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    broker_id INT UNSIGNED NOT NULL,
    full_name VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    age TINYINT UNSIGNED,
    listing_url VARCHAR(1000),
    is_active BOOLEAN DEFAULT TRUE,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_confirmed TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (broker_id) REFERENCES brokers(id) ON DELETE CASCADE
);
CREATE TABLE addresses (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    person_id INT UNSIGNED NOT NULL,
    address VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(10) DEFAULT 'US',
    is_current BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
);
CREATE TABLE phone_numbers (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    person_id INT UNSIGNED NOT NULL,
    phone VARCHAR(30),
    type ENUM('mobile', 'landline', 'unknown') DEFAULT 'unknown',
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
);
CREATE TABLE email_addresses (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    person_id INT UNSIGNED NOT NULL,
    email VARCHAR(255),
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
);
CREATE TABLE relatives (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    person_id INT UNSIGNED NOT NULL,
    name VARCHAR(255),
    relation VARCHAR(100),
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
);
CREATE TABLE employment (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    person_id INT UNSIGNED NOT NULL,
    employer VARCHAR(255),
    job_title VARCHAR(255),
    income_range VARCHAR(100),
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
);
CREATE TABLE social_profiles (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    person_id INT UNSIGNED NOT NULL,
    platform VARCHAR(100),
    profile_url VARCHAR(500),
    username VARCHAR(255),
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
);
CREATE TABLE scrape_jobs (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    broker_id INT UNSIGNED NOT NULL,
    status ENUM('running', 'completed', 'failed') DEFAULT 'running',
    records_scraped INT UNSIGNED DEFAULT 0,
    records_removed INT UNSIGNED DEFAULT 0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    error_message TEXT,
    FOREIGN KEY (broker_id) REFERENCES brokers(id) ON DELETE CASCADE
);
-- ── Views ──────────────────────────────────────────────────────────────
CREATE VIEW v_people_full AS
SELECT p.id,
    p.full_name,
    p.first_name,
    p.last_name,
    p.age,
    p.listing_url,
    p.first_seen,
    p.last_confirmed,
    b.name AS broker_name,
    b.website_url AS broker_url,
    b.opt_out_url,
    b.category AS broker_category,
    b.country AS broker_country,
    a.city,
    a.state,
    a.postal_code,
    a.country AS address_country,
    ph.phone,
    em.email
FROM people p
    JOIN brokers b ON b.id = p.broker_id
    LEFT JOIN addresses a ON a.id = (
        SELECT id
        FROM addresses
        WHERE person_id = p.id
            AND is_current = TRUE
        ORDER BY id ASC
        LIMIT 1
    )
    LEFT JOIN phone_numbers ph ON ph.id = (
        SELECT id
        FROM phone_numbers
        WHERE person_id = p.id
        ORDER BY id ASC
        LIMIT 1
    )
    LEFT JOIN email_addresses em ON em.id = (
        SELECT id
        FROM email_addresses
        WHERE person_id = p.id
        ORDER BY id ASC
        LIMIT 1
    )
WHERE p.is_active = TRUE;
CREATE VIEW v_broker_stats AS
SELECT b.id,
    b.name,
    b.website_url,
    b.category,
    b.country,
    b.last_scraped,
    COUNT(
        CASE
            WHEN p.is_active = TRUE THEN 1
        END
    ) AS active_listings,
    COUNT(
        CASE
            WHEN p.is_active = FALSE THEN 1
        END
    ) AS inactive_listings,
    MAX(p.last_confirmed) AS latest_confirmed
FROM brokers b
    LEFT JOIN people p ON p.broker_id = b.id
GROUP BY b.id,
    b.name,
    b.website_url,
    b.category,
    b.country,
    b.last_scraped;
-- ── Indexes ────────────────────────────────────────────────────────────
-- ── Core name indexes — used by the exposure search query ─────────────
-- These turn a full-table scan into a fast index lookup.
-- first_name + last_name composite index covers the most common search pattern.
CREATE INDEX idx_people_firstname ON people(first_name);
CREATE INDEX idx_people_lastname ON people(last_name);
CREATE INDEX idx_people_name_pair ON people(first_name, last_name);
-- composite: covers both at once
CREATE INDEX idx_people_fullname ON people(full_name);
CREATE INDEX idx_people_broker ON people(broker_id);
CREATE INDEX idx_people_active ON people(is_active);
CREATE INDEX idx_people_confirmed ON people(last_confirmed);
-- Composite index for the most common WHERE clause: active + name lookup
CREATE INDEX idx_people_active_last ON people(is_active, last_name);
-- ── Address indexes ────────────────────────────────────────────────────
CREATE INDEX idx_address_person ON addresses(person_id);
-- speeds up JOIN
CREATE INDEX idx_address_current ON addresses(person_id, is_current);
-- covers subquery
CREATE INDEX idx_address_city ON addresses(city);
CREATE INDEX idx_address_state ON addresses(state);
CREATE INDEX idx_address_country ON addresses(country);
-- ── Phone/email indexes ────────────────────────────────────────────────
CREATE INDEX idx_phone_person ON phone_numbers(person_id);
-- speeds up JOIN
CREATE INDEX idx_email_person ON email_addresses(person_id);
-- speeds up JOIN
CREATE INDEX idx_phone ON phone_numbers(phone);
CREATE INDEX idx_email ON email_addresses(email);
-- ── Other indexes ──────────────────────────────────────────────────────
CREATE INDEX idx_scrape_broker ON scrape_jobs(broker_id);
CREATE INDEX idx_scrape_status ON scrape_jobs(status);
CREATE INDEX idx_broker_country ON brokers(country);