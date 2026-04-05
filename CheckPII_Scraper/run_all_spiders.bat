@echo off
REM ============================================================
REM CheckPII — Run spiders in parallel
REM
REM Usage:
REM   run_all_spiders.bat                (working brokers only — recommended)
REM   run_all_spiders.bat working        (same as above)
REM   run_all_spiders.bat all            (all brokers incl. blocked ones)
REM   run_all_spiders.bat us             (US working only)
REM   run_all_spiders.bat ca             (Canada working only)
REM   run_all_spiders.bat uk             (UK working only)
REM
REM ── Broker status ────────────────────────────────────────────
REM   WORKING — confirmed accessible, no paywall on core data
REM   ID  1  Spokeo              US   ✅ WORKING
REM   ID  7  Radaris US          US   ✅ WORKING
REM   ID  8  TruthFinder         US   ✅ WORKING (text scan)
REM   ID  6  Intelius            US   ✅ WORKING (text scan)
REM   ID 20  TruePeopleSearch    US   ✅ WORKING (JSON-LD: phone+email)
REM   ID 21  FastPeopleSearch    US   ✅ WORKING (JSON-LD: phone+email)
REM   ID 22  ZabaSearch          US   ✅ WORKING (minimal protection)
REM   ID 23  ThatsThem           US   ✅ WORKING (JSON-LD: phone+email)
REM   ID 24  FamilyTreeNow       US   ✅ WORKING (relatives+address)
REM   ID 25  AnyWho              US   ✅ WORKING (AT&T directory)
REM   ID 26  PeekYou             US   ✅ WORKING (social profiles)
REM   ID 11  Canada411           CA   ✅ WORKING
REM   ID 14  411.ca              CA   ✅ WORKING
REM   ID 17  192.com             UK   ✅ WORKING
REM   --------------------------------------------------------
REM   BLOCKED — Cloudflare or full paywall, not worth running
REM   ID  2  Whitepages          US   ❌ BLOCKED
REM   ID  3  BeenVerified        US   ❌ BLOCKED
REM   ID  4  PeopleFinder        US   ❌ BLOCKED
REM   ID  5  MyLife              US   ❌ BLOCKED
REM   ID  9  Instantcheckmate    US   ❌ BLOCKED
REM   ID 10  USPhoneBook         US   ❌ BLOCKED
REM   ID 12  Radaris CA          CA   ❌ BLOCKED
REM   ID 13  Whitepages CA       CA   ❌ BLOCKED
REM   ID 15  CanadaPages         CA   ❌ BLOCKED
REM   ID 16  BT PhoneBook        UK   ❌ BLOCKED
REM   ID 18  WhitePages AU       AU   ❌ BLOCKED
REM   ID 19  Pipl                GL   ❌ API only
REM ============================================================

REM ── Node.js memory — prevents heap OOM crash after ~64k records ──────
set NODE_OPTIONS=--max-old-space-size=4096

set MODE=%1
if "%MODE%"=="" set MODE=working

if not exist crawls mkdir crawls

echo.
echo ===================================================
echo  CheckPII Spider Launcher
echo  Mode    : %MODE%
echo  Node RAM: %NODE_OPTIONS%
echo  Time    : %DATE% %TIME%
echo ===================================================
echo.

if /i "%MODE%"=="working" goto run_working
if /i "%MODE%"=="all"     goto run_all
if /i "%MODE%"=="us"      goto run_us_working
if /i "%MODE%"=="ca"      goto run_ca_working
if /i "%MODE%"=="uk"      goto run_uk_working
goto run_working

REM ════════════════════════════════════════════════════════════
REM  WORKING BROKERS ONLY (default)
REM ════════════════════════════════════════════════════════════

:run_working
echo [INFO] Launching confirmed-working brokers only...
echo [INFO] Skipping Cloudflare-blocked brokers (IDs 2-5, 9-10, 12-13, 15-16, 18-19)
echo.
call :run_us_working
call :run_ca_working
call :run_uk_working
goto done

REM ════════════════════════════════════════════════════════════
REM  ALL BROKERS (includes blocked — will mostly fail)
REM ════════════════════════════════════════════════════════════

:run_all
echo [WARN] Launching ALL brokers including Cloudflare-blocked ones.
echo [WARN] Blocked brokers will open windows but collect no data.
echo.
call :run_us_all
call :run_ca_all
call :run_uk_all
call :run_au_all
call :run_global_all
goto done

REM ════════════════════════════════════════════════════════════
REM  WORKING — US
REM ════════════════════════════════════════════════════════════

:run_us_working
echo [US] Starting working US brokers...
echo [US] JSON-LD brokers (phone+email): TruePeopleSearch, FastPeopleSearch, ThatsThem
echo [US] Directory brokers: Spokeo, Radaris, ZabaSearch, AnyWho
echo [US] Social/genealogy: PeekYou, FamilyTreeNow
start "Spokeo [✅]"              cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=1  -s JOBDIR=crawls/spokeo-1"
start "Radaris US [✅]"          cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=7  -s JOBDIR=crawls/radaris-7"
start "TruthFinder [✅]"         cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=8  -s JOBDIR=crawls/truthfinder-8"
start "Intelius [✅]"            cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=6  -s JOBDIR=crawls/intelius-6"
start "TruePeopleSearch [✅📞]"  cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=20 -s JOBDIR=crawls/truepeoplesearch-20"
start "FastPeopleSearch [✅📞]"  cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=21 -s JOBDIR=crawls/fastpeoplesearch-21"
start "ZabaSearch [✅]"          cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=22 -s JOBDIR=crawls/zabasearch-22"
start "ThatsThem [✅📞]"         cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=23 -s JOBDIR=crawls/thatsthem-23"
start "FamilyTreeNow [✅]"       cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=24 -s JOBDIR=crawls/familytreenow-24"
start "AnyWho [✅]"              cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=25 -s JOBDIR=crawls/anywho-25"
start "PeekYou [✅]"             cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=26 -s JOBDIR=crawls/peekyou-26"
exit /b

REM ════════════════════════════════════════════════════════════
REM  WORKING — Canada
REM ════════════════════════════════════════════════════════════

:run_ca_working
echo [CA] Starting: Canada411, 411.ca
start "Canada411 [CA-working]"     cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=11 -s JOBDIR=crawls/canada411-11"
start "411.ca [CA-working]"        cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=14 -s JOBDIR=crawls/411ca-14"
exit /b

REM ════════════════════════════════════════════════════════════
REM  WORKING — UK
REM ════════════════════════════════════════════════════════════

:run_uk_working
echo [UK] Starting: 192.com
start "192.com [UK-working]"       cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=17 -s JOBDIR=crawls/192com-17"
exit /b

REM ════════════════════════════════════════════════════════════
REM  ALL — US (includes blocked)
REM ════════════════════════════════════════════════════════════

:run_us_all
echo [US-ALL] Starting all US brokers...
start "Spokeo"           cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=1  -s JOBDIR=crawls/spokeo-1"
start "Whitepages"       cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=2  -s JOBDIR=crawls/whitepages-2"
start "BeenVerified"     cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=3  -s JOBDIR=crawls/beenverified-3"
start "PeopleFinder"     cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=4  -s JOBDIR=crawls/peoplefinder-4"
start "MyLife"           cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=5  -s JOBDIR=crawls/mylife-5"
start "Intelius"         cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=6  -s JOBDIR=crawls/intelius-6"
start "Radaris US"       cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=7  -s JOBDIR=crawls/radaris-7"
start "TruthFinder"      cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=8  -s JOBDIR=crawls/truthfinder-8"
start "Instantcheckmate" cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=9  -s JOBDIR=crawls/instantcheckmate-9"
start "USPhoneBook"      cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=10 -s JOBDIR=crawls/usphonebook-10"
exit /b

REM ════════════════════════════════════════════════════════════
REM  ALL — Canada (includes blocked)
REM ════════════════════════════════════════════════════════════

:run_ca_all
echo [CA-ALL] Starting all Canadian brokers...
start "Canada411"        cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=11 -s JOBDIR=crawls/canada411-11"
start "Radaris CA"       cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=12 -s JOBDIR=crawls/radaris-ca-12"
start "Whitepages CA"    cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=13 -s JOBDIR=crawls/whitepages-ca-13"
start "411.ca"           cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=14 -s JOBDIR=crawls/411ca-14"
start "CanadaPages"      cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=15 -s JOBDIR=crawls/canadapages-15"
exit /b

REM ════════════════════════════════════════════════════════════
REM  ALL — UK (includes blocked)
REM ════════════════════════════════════════════════════════════

:run_uk_all
echo [UK-ALL] Starting all UK brokers...
start "BT PhoneBook"     cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=16 -s JOBDIR=crawls/btphonebook-16"
start "192.com"          cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=17 -s JOBDIR=crawls/192com-17"
exit /b

REM ════════════════════════════════════════════════════════════
REM  ALL — Australia (includes blocked)
REM ════════════════════════════════════════════════════════════

:run_au_all
echo [AU-ALL] Starting all Australian brokers...
start "WhitePages AU"    cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=18 -s JOBDIR=crawls/whitepages-au-18"
exit /b

REM ════════════════════════════════════════════════════════════
REM  ALL — Global (includes blocked)
REM ════════════════════════════════════════════════════════════

:run_global_all
echo [GLOBAL-ALL] Starting global brokers...
start "Pipl"             cmd /k "set NODE_OPTIONS=%NODE_OPTIONS% && scrapy crawl broker_spider -a broker_id=19 -s JOBDIR=crawls/pipl-19"
exit /b

REM ════════════════════════════════════════════════════════════

:done
echo.
echo ===================================================
echo  Spiders launched. Each CMD window = one broker.
echo  Close any window to stop that spider.
echo  Crawl state saved — restart resumes where it left off.
echo ===================================================
echo.
pause