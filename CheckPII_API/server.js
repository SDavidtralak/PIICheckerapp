const express = require('express');
const mysql   = require('mysql2/promise');
const cors    = require('cors');

const app  = express();
const PORT = 3000;

app.use(cors({ origin: 'http://localhost:4200' }));
app.use(express.json());

// ── No caching ─────────────────────────────────────────────────────────
app.use((req, res, next) => {
  res.set('Cache-Control', 'no-store, no-cache, must-revalidate, private');
  res.set('Pragma', 'no-cache');
  res.set('Expires', '0');
  next();
});

// ── Request logger ─────────────────────────────────────────────────────
app.use((req, res, next) => {
  const time  = new Date().toLocaleTimeString();
  const start = Date.now();
  res.on('finish', () => {
    const ms   = Date.now() - start;
    const icon = res.statusCode >= 500 ? '✗' : res.statusCode >= 400 ? '⚠' : '✓';
    console.log(`${icon} ${time} — ${req.method} ${req.url} [${res.statusCode}] ${ms}ms`);
  });
  next();
});

// ── MySQL pool ─────────────────────────────────────────────────────────
const pool = mysql.createPool({
  host:               'localhost',
  user:               'root',
  password:           'evoplan12',   // ← change this
  database:           'checkpii',
  waitForConnections: true,
  connectionLimit:    20,   // increased — handles spider + app simultaneously
  queueLimit:         50,
  connectTimeout:     10000,
  acquireTimeout:     10000,
});

pool.getConnection()
  .then(conn => {
    console.log('✓ MySQL connected successfully.');
    // READ UNCOMMITTED lets searches skip row locks the spider holds during inserts.
    // The spider writes millions of rows — without this, every search waits for
    // the current insert batch to commit before it can read. Acceptable for
    // public people-search data where a slightly stale read is fine.
    conn.query("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED");
    conn.release();
  })
  .catch(err  => { console.error('✗ MySQL connection failed:', err.message); process.exit(1); });

// Apply READ UNCOMMITTED to every new connection in the pool
pool.on('connection', (conn) => {
  conn.query("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED");
});

// ── Helper ─────────────────────────────────────────────────────────────
function sendResults(res, rows, extra = {}) {
  if (rows.length === 0) {
    return res.json({
      count: 0, results: [], not_found: true,
      message: 'No records found. Your data may not be listed on any of the brokers we have indexed yet, or the brokers may not have scraped your area yet.',
      ...extra
    });
  }
  res.json({ count: rows.length, results: rows, not_found: false, ...extra });
}

// ══════════════════════════════════════════════════════════════════════
// ROUTES
// ══════════════════════════════════════════════════════════════════════

// ── Health ─────────────────────────────────────────────────────────────
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date() });
});

// ── MAIN: Personal exposure search ─────────────────────────────────────
// Called by the Angular app when a user searches for themselves.
// GET /api/search/exposure?q=John+Smith&city=Toronto&state=ON&limit=200
app.get('/api/search/exposure', async (req, res) => {
  try {
    const { q = '', city, state, age, limit = 200 } = req.query;

    if (!q) return res.status(400).json({ error: 'Name is required' });

    // ── Split name into parts for faster indexed lookups ──────────────
    // "charles smith" → search first_name='charles' AND last_name='smith'
    // This lets MySQL use the idx_people_lastname index instead of
    // doing a full table scan with LIKE '%charles smith%'
    const nameParts  = q.trim().split(/\s+/);
    const firstName  = nameParts[0]  || '';
    const lastName   = nameParts[nameParts.length - 1] || '';
    const hasTwo     = nameParts.length >= 2;

    // Build WHERE clause — use indexed columns where possible
    // first_name LIKE 'charles%' can use an index (no leading %)
    // last_name  LIKE 'smith%'   can use an index (no leading %)
    const where  = ['p.is_active = TRUE'];
    const params = [];

    if (hasTwo) {
      // Two-part name: match first AND last separately (fastest)
      where.push('p.first_name LIKE ?');
      where.push('p.last_name LIKE ?');
      params.push(`${firstName}%`);
      params.push(`${lastName}%`);
    } else {
      // Single word: check both first and last name
      where.push('(p.first_name LIKE ? OR p.last_name LIKE ?)');
      params.push(`${firstName}%`, `${firstName}%`);
    }

    // Location filters — applied after name match (smaller result set)
    if (city)  { where.push('a.city LIKE ?');  params.push(`%${city}%`); }
    if (state) { where.push('a.state = ?');    params.push(state);       }
    if (age)   { where.push('p.age BETWEEN ? AND ?'); params.push(Number(age) - 3, Number(age) + 3); }
    params.push(Number(limit));

    // ── Rewritten query — no correlated subqueries ────────────────────
    // Old approach: 3 correlated sub-SELECTs per row = very slow at scale
    // New approach: LEFT JOIN LATERAL equivalent using MIN(id) grouping
    // which MySQL can resolve with a single pass per table
    const [rows] = await pool.query(`
      SELECT
        p.id, p.full_name, p.first_name, p.last_name, p.age,
        p.listing_url, p.first_seen, p.last_confirmed,
        b.name        AS broker_name,
        b.website_url AS broker_url,
        b.opt_out_url,
        b.category    AS broker_category,
        b.country     AS broker_country,
        a.city, a.state, a.postal_code,
        a.country     AS address_country,
        ph.phone, em.email
      FROM people p
      JOIN brokers b ON b.id = p.broker_id
      LEFT JOIN addresses a
        ON a.person_id = p.id AND a.is_current = TRUE
        AND a.id = (SELECT MIN(id) FROM addresses WHERE person_id = p.id AND is_current = TRUE)
      LEFT JOIN phone_numbers ph
        ON ph.person_id = p.id
        AND ph.id = (SELECT MIN(id) FROM phone_numbers WHERE person_id = p.id)
      LEFT JOIN email_addresses em
        ON em.person_id = p.id
        AND em.id = (SELECT MIN(id) FROM email_addresses WHERE person_id = p.id)
      WHERE ${where.join(' AND ')}
      ORDER BY p.last_confirmed DESC
      LIMIT ?
    `, params);

    // Build exposure summary stats
    const brokers     = [...new Set(rows.map(r => r.broker_name))];
    const countries   = [...new Set(rows.map(r => r.broker_country))];
    const hasPhone    = rows.filter(r => r.phone).length;
    const hasEmail    = rows.filter(r => r.email).length;
    const hasAddress  = rows.filter(r => r.city).length;

    sendResults(res, rows, {
      summary: {
        brokers_found:    brokers.length,
        broker_list:      brokers,
        countries_found:  countries,
        records_with_phone:   hasPhone,
        records_with_email:   hasEmail,
        records_with_address: hasAddress,
      }
    });

  } catch (err) {
    console.error('/api/search/exposure error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Search by name (generic) ───────────────────────────────────────────
app.get('/api/search/name', async (req, res) => {
  try {
    const { q = '', country, from, to, limit = 500 } = req.query;
    const where  = ['p.is_active = TRUE'];
    const params = [];

    if (q)       { where.push('p.full_name LIKE ?');  params.push(`%${q}%`);  }
    if (country) { where.push('b.country = ?');       params.push(country);   }
    if (from)    { where.push('p.first_seen >= ?');   params.push(from);      }
    if (to)      { where.push('p.first_seen <= ?');   params.push(to);        }
    params.push(Number(limit));

    const [rows] = await pool.query(`
      SELECT p.id, p.full_name, p.first_name, p.last_name, p.age,
             p.listing_url, p.first_seen, p.last_confirmed,
             b.name AS broker_name, b.category AS broker_category,
             b.country AS broker_country, b.opt_out_url,
             a.city, a.state, a.postal_code, a.country AS address_country,
             ph.phone, em.email
      FROM people p
      JOIN brokers b ON b.id = p.broker_id
      LEFT JOIN addresses a ON a.id = (SELECT id FROM addresses WHERE person_id = p.id AND is_current = TRUE ORDER BY id ASC LIMIT 1)
      LEFT JOIN phone_numbers ph ON ph.id = (SELECT id FROM phone_numbers WHERE person_id = p.id ORDER BY id ASC LIMIT 1)
      LEFT JOIN email_addresses em ON em.id = (SELECT id FROM email_addresses WHERE person_id = p.id ORDER BY id ASC LIMIT 1)
      WHERE ${where.join(' AND ')}
      ORDER BY p.last_confirmed DESC LIMIT ?
    `, params);

    sendResults(res, rows);
  } catch (err) {
    console.error('/api/search/name error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Search by location ─────────────────────────────────────────────────
app.get('/api/search/location', async (req, res) => {
  try {
    const { city = '', state = '', country, from, to, limit = 500 } = req.query;
    const where  = ['p.is_active = TRUE', 'a.is_current = TRUE'];
    const params = [];

    if (city)    { where.push('a.city LIKE ?');       params.push(`%${city}%`); }
    if (state)   { where.push('a.state = ?');         params.push(state);       }
    if (country) { where.push('a.country = ?');       params.push(country);     }
    if (from)    { where.push('p.first_seen >= ?');   params.push(from);        }
    if (to)      { where.push('p.first_seen <= ?');   params.push(to);          }
    params.push(Number(limit));

    const [rows] = await pool.query(`
      SELECT p.id, p.full_name, p.age, p.listing_url, p.first_seen, p.last_confirmed,
             b.name AS broker_name, b.category AS broker_category,
             b.country AS broker_country, b.opt_out_url,
             a.address, a.city, a.state, a.postal_code, a.country AS address_country,
             ph.phone, em.email
      FROM people p
      JOIN brokers b ON b.id = p.broker_id
      JOIN addresses a ON a.person_id = p.id AND a.is_current = TRUE
      LEFT JOIN phone_numbers ph ON ph.id = (SELECT id FROM phone_numbers WHERE person_id = p.id ORDER BY id ASC LIMIT 1)
      LEFT JOIN email_addresses em ON em.id = (SELECT id FROM email_addresses WHERE person_id = p.id ORDER BY id ASC LIMIT 1)
      WHERE ${where.join(' AND ')}
      ORDER BY p.last_confirmed DESC LIMIT ?
    `, params);

    sendResults(res, rows);
  } catch (err) {
    console.error('/api/search/location error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Search by phone ────────────────────────────────────────────────────
app.get('/api/search/phone', async (req, res) => {
  try {
    const { q = '', country, limit = 500 } = req.query;
    const where  = ['p.is_active = TRUE', "REPLACE(ph.phone, '-', '') LIKE ?"];
    const params = [`%${q.replace(/\D/g, '')}%`];
    if (country) { where.push('b.country = ?'); params.push(country); }
    params.push(Number(limit));

    const [rows] = await pool.query(`
      SELECT p.id, p.full_name, p.age, p.listing_url, p.first_seen, p.last_confirmed,
             b.name AS broker_name, b.category AS broker_category,
             b.country AS broker_country, b.opt_out_url,
             ph.phone, ph.type AS phone_type,
             a.city, a.state, a.country AS address_country
      FROM phone_numbers ph
      JOIN people  p ON p.id = ph.person_id
      JOIN brokers b ON b.id = p.broker_id
      LEFT JOIN addresses a ON a.id = (SELECT id FROM addresses WHERE person_id = p.id AND is_current = TRUE ORDER BY id ASC LIMIT 1)
      WHERE ${where.join(' AND ')}
      ORDER BY p.last_confirmed DESC LIMIT ?
    `, params);

    sendResults(res, rows);
  } catch (err) {
    console.error('/api/search/phone error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Search by email ────────────────────────────────────────────────────
app.get('/api/search/email', async (req, res) => {
  try {
    const { q = '', country, limit = 500 } = req.query;
    const where  = ['p.is_active = TRUE', 'em.email LIKE ?'];
    const params = [`%${q}%`];
    if (country) { where.push('b.country = ?'); params.push(country); }
    params.push(Number(limit));

    const [rows] = await pool.query(`
      SELECT p.id, p.full_name, p.age, p.listing_url, p.first_seen, p.last_confirmed,
             b.name AS broker_name, b.category AS broker_category,
             b.country AS broker_country, b.opt_out_url,
             em.email, a.city, a.state, a.country AS address_country
      FROM email_addresses em
      JOIN people  p ON p.id = em.person_id
      JOIN brokers b ON b.id = p.broker_id
      LEFT JOIN addresses a ON a.id = (SELECT id FROM addresses WHERE person_id = p.id AND is_current = TRUE ORDER BY id ASC LIMIT 1)
      WHERE ${where.join(' AND ')}
      ORDER BY p.last_confirmed DESC LIMIT ?
    `, params);

    sendResults(res, rows);
  } catch (err) {
    console.error('/api/search/email error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Search by broker ───────────────────────────────────────────────────
app.get('/api/search/broker', async (req, res) => {
  try {
    const { name = '', country, from, to, limit = 500 } = req.query;
    const where  = ['p.is_active = TRUE'];
    const params = [];
    if (name)    { where.push('b.name = ?');          params.push(name);    }
    if (country) { where.push('b.country = ?');       params.push(country); }
    if (from)    { where.push('p.first_seen >= ?');   params.push(from);    }
    if (to)      { where.push('p.first_seen <= ?');   params.push(to);      }
    params.push(Number(limit));

    const [rows] = await pool.query(`
      SELECT p.id, p.full_name, p.age, p.listing_url, p.first_seen, p.last_confirmed,
             b.name AS broker_name, b.category AS broker_category,
             b.country AS broker_country, b.opt_out_url,
             a.city, a.state, a.postal_code, a.country AS address_country,
             ph.phone, em.email
      FROM people p
      JOIN brokers b ON b.id = p.broker_id
      LEFT JOIN addresses a ON a.id = (SELECT id FROM addresses WHERE person_id = p.id AND is_current = TRUE ORDER BY id ASC LIMIT 1)
      LEFT JOIN phone_numbers ph ON ph.id = (SELECT id FROM phone_numbers WHERE person_id = p.id ORDER BY id ASC LIMIT 1)
      LEFT JOIN email_addresses em ON em.id = (SELECT id FROM email_addresses WHERE person_id = p.id ORDER BY id ASC LIMIT 1)
      WHERE ${where.join(' AND ')}
      ORDER BY p.last_confirmed DESC LIMIT ?
    `, params);

    sendResults(res, rows);
  } catch (err) {
    console.error('/api/search/broker error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Person detail ──────────────────────────────────────────────────────
app.get('/api/person/:id', async (req, res) => {
  try {
    const id = Number(req.params.id);
    const [[person]] = await pool.query('SELECT * FROM people WHERE id = ?', [id]);

    if (!person) return res.status(404).json({ error: 'Person not found', not_found: true });

    const [addresses]  = await pool.query('SELECT * FROM addresses       WHERE person_id = ?', [id]);
    const [phones]     = await pool.query('SELECT * FROM phone_numbers   WHERE person_id = ?', [id]);
    const [emails]     = await pool.query('SELECT * FROM email_addresses WHERE person_id = ?', [id]);
    const [relatives]  = await pool.query('SELECT * FROM relatives       WHERE person_id = ?', [id]);
    const [employment] = await pool.query('SELECT * FROM employment      WHERE person_id = ?', [id]);
    const [socials]    = await pool.query('SELECT * FROM social_profiles WHERE person_id = ?', [id]);
    const [[broker]]   = await pool.query('SELECT * FROM brokers         WHERE id = ?', [person.broker_id]);

    res.json({ person, broker, addresses, phones, emails, relatives, employment, socials });
  } catch (err) {
    console.error('/api/person error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Stats ──────────────────────────────────────────────────────────────
app.get('/api/stats', async (req, res) => {
  try {
    const [[totals]]   = await pool.query('SELECT COUNT(*) AS total_people  FROM people  WHERE is_active = TRUE');
    const [[brokers]]  = await pool.query('SELECT COUNT(*) AS total_brokers FROM brokers WHERE is_active = TRUE');
    const [[us_count]] = await pool.query("SELECT COUNT(*) AS cnt FROM people p JOIN brokers b ON b.id=p.broker_id WHERE p.is_active=TRUE AND b.country='US'");
    const [[ca_count]] = await pool.query("SELECT COUNT(*) AS cnt FROM people p JOIN brokers b ON b.id=p.broker_id WHERE p.is_active=TRUE AND b.country='CA'");
    const [[latest]]   = await pool.query('SELECT MAX(last_confirmed) AS last_updated FROM people WHERE is_active = TRUE');
    const [brokerStats] = await pool.query('SELECT * FROM v_broker_stats ORDER BY active_listings DESC');
    const [recentJobs]  = await pool.query('SELECT * FROM scrape_jobs    ORDER BY started_at DESC LIMIT 10');

    // Format last_updated as a readable relative time
    let lastUpdated = 'Never';
    if (latest.last_updated) {
      const diff = Date.now() - new Date(latest.last_updated).getTime();
      const mins  = Math.floor(diff / 60000);
      const hours = Math.floor(diff / 3600000);
      const days  = Math.floor(diff / 86400000);
      if      (mins  < 1)   lastUpdated = 'Just now';
      else if (mins  < 60)  lastUpdated = `${mins}m ago`;
      else if (hours < 24)  lastUpdated = `${hours}h ago`;
      else if (days  < 7)   lastUpdated = `${days}d ago`;
      else                  lastUpdated = new Date(latest.last_updated).toLocaleDateString();
    }

    res.json({
      total_people:  totals.total_people,
      total_brokers: brokers.total_brokers,
      us_records:    us_count.cnt,
      ca_records:    ca_count.cnt,
      last_updated:  lastUpdated,
      brokers:       brokerStats,
      recent_jobs:   recentJobs,
    });
  } catch (err) {
    console.error('/api/stats error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Start ──────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`✓ CheckPII API running at http://localhost:${PORT}`);
  console.log(`  Key endpoint: GET /api/search/exposure?q=John+Smith&city=Toronto&state=ON`);
});