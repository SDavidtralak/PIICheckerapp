# 🛡 CheckPII — Personal Data Exposure Scanner

> Search data broker databases to find where your personal information is listed — and remove it.

![Stack](https://img.shields.io/badge/Angular-21-dd0031?style=flat-square&logo=angular)
![Stack](https://img.shields.io/badge/Node.js-Express-339933?style=flat-square&logo=node.js)
![Stack](https://img.shields.io/badge/MySQL-8.0-4479a1?style=flat-square&logo=mysql)
![Stack](https://img.shields.io/badge/Python-Scrapy-3776ab?style=flat-square&logo=python)
![Stack](https://img.shields.io/badge/Playwright-Stealth-2d4a6e?style=flat-square)

---

## What It Does

CheckPII scrapes public data broker websites, indexes the results into a local MySQL database, and lets users search for their own name to see where their personal information is exposed. It then guides them through the opt-out process for each broker.

**No data is ever sent to a third party. Everything runs locally on your machine.**

---

## Architecture

```
Scrapy Spider (Python)
       │
       ▼
  MySQL Database  ◄──────►  Express API (Node.js)  ◄──────►  Angular App
  localhost:3306             localhost:3000                   localhost:4200
```

The spider runs in the background scraping broker sites and writing records to MySQL. The Angular app queries the Express API on demand. The two are completely independent — you can search the app while spiders are actively scraping.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Database Setup](#database-setup)
- [Express API Setup](#express-api-setup)
- [Angular App Setup](#angular-app-setup)
- [Spider Setup](#spider-setup)
- [Daily Launch Order](#daily-launch-order)
- [Broker Reference](#broker-reference)
- [Proxy & Anti-Detection](#proxy--anti-detection)
- [Database Backup & Restore](#database-backup--restore)
- [Troubleshooting](#troubleshooting)
- [Useful Commands](#useful-commands)

---

## Prerequisites

Install all of the following before proceeding:

| Tool        | Version | Download                                               |
| ----------- | ------- | ------------------------------------------------------ |
| Node.js     | 20+ LTS | [nodejs.org](https://nodejs.org/en/download)           |
| Python      | 3.12+   | [python.org](https://www.python.org/downloads)         |
| MySQL       | 8.0     | [dev.mysql.com](https://dev.mysql.com/downloads/mysql) |
| Git         | Latest  | [git-scm.com](https://git-scm.com/downloads)           |
| Angular CLI | Latest  | `npm install -g @angular/cli`                          |

### Add MySQL to System PATH (Windows)

Open PowerShell as Administrator:

```powershell
[System.Environment]::SetEnvironmentVariable(
  "Path",
  [System.Environment]::GetEnvironmentVariable("Path","Machine") +
  ";C:\Program Files\MySQL\MySQL Server 8.0\bin",
  "Machine"
)
```

Close and reopen PowerShell, then verify:

```powershell
mysql --version
mysqldump --version
```

---

## Project Structure

```
CheckPII\
├── CheckPIIapp\              ← Angular frontend
├── CheckPII_API\             ← Express REST API
└── CheckPII_Scraper\         ← Python Scrapy spiders
    ├── CheckPII_Scraper\
    │   ├── spiders\
    │   │   └── broker_spider.py
    │   ├── pipelines.py
    │   ├── settings.py
    │   ├── connection_monitor.py
    │   ├── proxy_rotator.py
    │   ├── items.py
    │   └── __init__.py
    ├── schema.sql
    ├── run_all_spiders.bat
    └── backup_db.bat
```

---

## Database Setup

### 1. Start MySQL

MySQL runs as a Windows service and starts automatically on boot. To check:

```powershell
Get-Service | Where-Object {$_.Name -like "*mysql*"}
```

If stopped:

```powershell
net start MySQL80
```

### 2. Create the Database

```powershell
mysql -u root -p
```

```sql
CREATE DATABASE checkpii;
exit
```

### 3. Load the Schema

```powershell
cd C:\Users\YourName\Desktop\CheckPII\CheckPII_Scraper
cmd /c "mysql -u root -p checkpii < schema.sql"
```

### 4. Set Your Password

> ⚠️ **Important** — replace `your_password_here` in both of these files:
>
> - `CheckPII_API\server.js` — line ~35: `password: 'your_password_here'`
> - `CheckPII_Scraper\CheckPII_Scraper\pipelines.py` — line ~35: `password = 'your_password_here'`

---

## Express API Setup

### 1. Install Dependencies

```powershell
cd C:\Users\YourName\Desktop\CheckPII\CheckPII_API
npm install express mysql2 cors
```

### 2. Start the API

```powershell
node server.js
```

Expected output:

```
✓ CheckPII API running at http://localhost:3000
✓ MySQL connected successfully.
```

> The API must be running before the Angular app will show as Connected. Test it at: http://localhost:3000/api/health

---

## Angular App Setup

### 1. Create the Project

```powershell
cd C:\Users\YourName\Desktop\CheckPII
ng new CheckPIIapp --routing=false --style=css --standalone
cd CheckPIIapp
```

### 2. Place the App Files

Copy these files into `src/app/` replacing any generated defaults:

- `app.ts`
- `app.html`
- `app.css`
- `app.config.ts`

Copy `index.html` into `src/` replacing the generated one.

### 3. Verify app.config.ts

Make sure `app.config.ts` contains `provideHttpClient`:

```typescript
import { ApplicationConfig } from '@angular/core';
import { provideHttpClient, withFetch } from '@angular/common/http';

export const appConfig: ApplicationConfig = {
  providers: [provideHttpClient(withFetch())],
};
```

### 4. Fix the Background Color

Open `src/styles.css` and add:

```css
html,
body {
  margin: 0;
  padding: 0;
  background: #050608;
  min-height: 100vh;
  color: #e2e8f0;
}
```

### 5. Start the App

```powershell
ng serve
```

Wait for `Application bundle generation complete` then open http://localhost:4200

---

## Spider Setup

### 1. Install Python Dependencies

```powershell
cd C:\Users\YourName\Desktop\CheckPII\CheckPII_Scraper
pip install scrapy scrapy-playwright scrapy-user-agents mysql-connector-python
pip install --user tf-playwright-stealth
playwright install chromium
```

### 2. Verify Stealth is Working

```powershell
python -c "from playwright_stealth import stealth_async; print('OK')"
```

### 3. Run a Test Spider

```powershell
scrapy crawl broker_spider -a broker_id=24 -s JOBDIR=crawls/familytreenow-24
```

You should see `[Spider] playwright-stealth loaded OK` and records being saved within a few seconds if the site is accessible.

### 4. Run All Working Spiders

```powershell
.\run_all_spiders.bat
```

This opens a separate CMD window for each broker. Close any window to stop that spider. Crawl state is saved automatically — restart resumes where it left off.

### Run Specific Regions

```powershell
.\run_all_spiders.bat us      # US brokers only
.\run_all_spiders.bat ca      # Canadian brokers only
.\run_all_spiders.bat uk      # UK brokers only
.\run_all_spiders.bat all     # All brokers including blocked ones
```

### Stop All Spiders

```powershell
Get-Process python | Stop-Process -Force
```

---

## Daily Launch Order

Every time you want to use CheckPII:

1. **MySQL** — starts automatically, nothing to do
2. **Start the API:**
   ```powershell
   cd CheckPII_API
   node server.js
   # Wait for: ✓ MySQL connected successfully.
   ```
3. **Start Angular:**
   ```powershell
   cd CheckPIIapp
   ng serve
   # Wait for: Application bundle generation complete.
   ```
4. **Open** http://localhost:4200
5. **(Optional) Start spiders:**
   ```powershell
   cd CheckPII_Scraper
   .\run_all_spiders.bat
   ```

---

## Broker Reference

### ✅ Working Brokers

| ID  | Broker           | Country | Data Available           | Notes                  |
| --- | ---------------- | ------- | ------------------------ | ---------------------- |
| 1   | Spokeo           | 🇺🇸 US   | Name, city, age          | Alphabetical directory |
| 6   | Intelius         | 🇺🇸 US   | Name, location           | Text scan              |
| 7   | Radaris US       | 🇺🇸 US   | Name, location           | Text scan              |
| 8   | TruthFinder      | 🇺🇸 US   | Name, location           | Text scan              |
| 20  | TruePeopleSearch | 🇺🇸 US   | Name, phone, email       | JSON-LD schema         |
| 21  | FastPeopleSearch | 🇺🇸 US   | Name, phone, email       | JSON-LD + FAQPage      |
| 22  | ZabaSearch       | 🇺🇸 US   | Name, phone              | Minimal protection     |
| 23  | ThatsThem        | 🇺🇸 US   | Name, phone, email       | JSON-LD schema         |
| 24  | FamilyTreeNow    | 🇺🇸 US   | Name, relatives, address | Genealogy data         |
| 25  | AnyWho           | 🇺🇸 US   | Name, phone              | AT&T directory         |
| 26  | PeekYou          | 🇺🇸 US   | Name, social profiles    | Online presence        |
| 11  | Canada411        | 🇨🇦 CA   | Name, phone              | Public directory       |
| 14  | 411.ca           | 🇨🇦 CA   | Name, phone              | Public directory       |
| 17  | 192.com          | 🇬🇧 UK   | Name, phone, address     | Public directory       |

### ❌ Blocked Brokers (Cloudflare)

IDs 2–5, 9–10, 12–13, 15–16, 18–19 — Whitepages, BeenVerified, MyLife, InstantCheckmate, etc. These require a paid proxy service like ScraperAPI to bypass.

---

## Proxy & Anti-Detection

### Stealth Mode

The spider automatically applies `tf-playwright-stealth` to every page request, patching:

- `navigator.webdriver` → false
- Canvas and WebGL fingerprints → randomized
- Plugin list → spoofed real browser plugins
- Chrome runtime object → injected
- Screen dimensions → 1920×1080
- Hardware concurrency and device memory → realistic values

### Proxy Configuration

Edit `PROXY_MODE` in `CheckPII_Scraper\CheckPII_Scraper\settings.py`:

```python
PROXY_MODE = 'off'        # Use your own IP or VPN (default)
PROXY_MODE = 'free'       # Rotate through free public proxies (~30% reliable)
PROXY_MODE = 'scraperapi' # ScraperAPI paid service (most reliable, $30/mo)
```

For ScraperAPI, add your key in `proxy_rotator.py`:

```python
SCRAPERAPI_KEY = 'your_api_key_here'
```

> **Note:** If using ProtonVPN or another VPN app, keep `PROXY_MODE = 'off'` — the VPN handles IP routing at the OS level automatically.

---

## Database Backup & Restore

### Setup backup_db.bat

Open `backup_db.bat` and set your MySQL password:

```bat
set MYSQL_PASS=your_actual_password_here
```

### Manual Backup

```powershell
cd CheckPII_Scraper
.\backup_db.bat
```

Saves a timestamped `.sql` file to `backups\`. Keeps the 10 most recent automatically.

### Restore from Backup

```powershell
mysql -u root -p checkpii < backups\checkpii_2026-04-02_123456.sql
```

### Full Database Reset

```powershell
mysql -u root -p
```

```sql
DROP DATABASE checkpii;
CREATE DATABASE checkpii;
exit
```

```powershell
cmd /c "mysql -u root -p checkpii < schema.sql"
```

### Data-Loss Protections

The pipeline has three built-in protections against accidental data deletion:

1. **Delayed mark** — records only marked inactive after the first successful page scrape. If the spider is blocked on page 1, nothing is ever marked.
2. **Minimum threshold** — sweep deletion only runs if at least 100 records were confirmed this run.
3. **Percentage guard** — sweep aborted if it would delete more than 50% of existing records (indicates the site was blocking, not that records are stale).

---

## Troubleshooting

### App shows "API Offline"

- Make sure `node server.js` is running
- Check the API terminal for MySQL connection errors
- Verify the password in `server.js` matches your MySQL root password
- Test directly: http://localhost:3000/api/health

### Spider gets 0 records immediately

The site is blocking your IP. Options:

- Try a mobile hotspot (different IP range, usually unblocked)
- Switch to `PROXY_MODE = 'free'` in `settings.py`
- Debug with: `scrapy crawl broker_spider -a broker_id=24 -s LOG_LEVEL=DEBUG`

### playwright-stealth import error

```powershell
pip uninstall playwright-stealth
pip install --user tf-playwright-stealth
python -c "from playwright_stealth import stealth_async; print('OK')"
```

### MySQL "too many connections"

```sql
SET GLOBAL max_connections = 300;
UPDATE scrape_jobs SET status='failed', completed_at=NOW() WHERE status='running';
```

### "yield from not allowed in async function"

Replace `broker_spider.py` with the latest version — an old file is present.

### Add missing indexes to an existing database

```sql
ALTER TABLE people ADD INDEX idx_people_firstname (first_name);
ALTER TABLE people ADD INDEX idx_people_name_pair (first_name, last_name);
ALTER TABLE people ADD INDEX idx_people_active_last (is_active, last_name);
ALTER TABLE addresses ADD INDEX idx_address_person (person_id);
ALTER TABLE addresses ADD INDEX idx_address_current (person_id, is_current);
ALTER TABLE phone_numbers ADD INDEX idx_phone_person (person_id);
ALTER TABLE email_addresses ADD INDEX idx_email_person (person_id);
```

---

## Useful Commands

### MySQL

```sql
-- Count records per broker
SELECT b.name, COUNT(p.id) AS records
FROM people p JOIN brokers b ON b.id = p.broker_id
GROUP BY b.name ORDER BY records DESC;

-- Total active records
SELECT COUNT(*) FROM people WHERE is_active = TRUE;

-- Reset stuck scrape jobs
UPDATE scrape_jobs SET status='failed', completed_at=NOW() WHERE status='running';
```

### Spider

```powershell
# Run a single broker with resume support
scrapy crawl broker_spider -a broker_id=1 -s JOBDIR=crawls/spokeo-1

# Stop all running spiders
Get-Process python | Stop-Process -Force

# Reset crawl state (forces full re-scrape next run)
Remove-Item -Recurse -Force crawls
```

### Angular

```powershell
# Development server
ng serve

# Production build
ng build --configuration=production
```

---

## API Endpoints

| Method | Endpoint                                                  | Description          |
| ------ | --------------------------------------------------------- | -------------------- |
| GET    | `/api/health`                                             | Health check         |
| GET    | `/api/stats`                                              | Database statistics  |
| GET    | `/api/search/exposure?q=John+Smith&city=Toronto&state=ON` | Main search endpoint |
| GET    | `/api/search/name?q=Smith&country=US`                     | Search by name       |
| GET    | `/api/search/location?city=Toronto&state=ON`              | Search by location   |
| GET    | `/api/search/phone?q=416-555-1234`                        | Search by phone      |
| GET    | `/api/search/email?q=john@example.com`                    | Search by email      |
| GET    | `/api/person/:id`                                         | Full record detail   |

---

_Built with Angular · Node.js · MySQL · Scrapy · Playwright_
