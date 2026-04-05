import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpParams } from '@angular/common/http';

// ── Interfaces ─────────────────────────────────────────────────────────
interface SearchForm {
  firstName:  string;
  lastName:   string;
  city:       string;
  province:   string;
  age:        string;
  phone:      string;
  email:      string;
}

interface ExposureRecord {
  id:               number;
  full_name:        string;
  age:              number;
  city:             string;
  state:            string;
  postal_code:      string;
  address_country:  string;
  phone:            string;
  email:            string;
  broker_name:      string;
  broker_country:   string;
  listing_url:      string;
  opt_out_url:      string;
  first_seen:       string;
  last_confirmed:   string;
  opt_out_status:   'pending' | 'opened' | 'automated' | 'done';
}

interface ScanResult {
  total_found:   number;
  brokers_found: number;
  records:       ExposureRecord[];
  not_found:     boolean;
  message?:      string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrls: ['./app.css']
})
export class AppComponent implements OnInit {

  private readonly API = 'http://localhost:3000/api';

  // ── Form ───────────────────────────────────────────────────────────
  form: SearchForm = {
    firstName: '', lastName: '', city: '',
    province: '', age: '', phone: '', email: ''
  };

  // ── State ──────────────────────────────────────────────────────────
  isScanning    = false;
  scanComplete  = false;
  notFound      = false;
  notFoundMsg   = '';
  progressPct   = 0;
  progressLabel = '';
  stepState: ('idle' | 'active' | 'done')[] = ['idle','idle','idle','idle'];

  // ── API status ─────────────────────────────────────────────────────
  apiConnected  = false;
  dbStats: any  = null;

  // ── Results ────────────────────────────────────────────────────────
  scanResult: ScanResult | null = null;
  selectedRecord: ExposureRecord | null = null;
  automationRunning = false;
  automationLog: string[] = [];

  // ── Opt-out automation config per broker ───────────────────────────
  readonly optOutConfig: Record<string, {
    method:  'link' | 'form' | 'email';
    url:     string;
    steps?:  string[];
  }> = {
    'Spokeo':           { method: 'form',  url: 'https://www.spokeo.com/optout',
      steps: ['Go to opt-out page', 'Enter your listing URL', 'Enter your email', 'Submit request', 'Confirm via email'] },
    'Whitepages':       { method: 'form',  url: 'https://www.whitepages.com/suppression-requests',
      steps: ['Go to opt-out page', 'Search for your listing', 'Click "Remove my listing"', 'Verify by phone'] },
    'BeenVerified':     { method: 'form',  url: 'https://www.beenverified.com/app/optout',
      steps: ['Go to opt-out page', 'Search your name', 'Select your record', 'Submit removal'] },
    'PeopleFinder':     { method: 'form',  url: 'https://www.peoplefinders.com/opt-out',
      steps: ['Go to opt-out page', 'Enter your details', 'Submit removal request'] },
    'MyLife':           { method: 'form',  url: 'https://www.mylife.com/ccpa/index.pubview',
      steps: ['Go to opt-out page', 'Fill out removal form', 'Submit'] },
    'Intelius':         { method: 'form',  url: 'https://www.intelius.com/opt-out',
      steps: ['Go to opt-out page', 'Search your name', 'Select record', 'Submit opt-out'] },
    'Radaris US':       { method: 'form',  url: 'https://radaris.com/control/privacy',
      steps: ['Create free account', 'Claim your profile', 'Request removal'] },
    'TruthFinder':      { method: 'form',  url: 'https://www.truthfinder.com/opt-out/',
      steps: ['Go to opt-out page', 'Enter your details', 'Submit removal'] },
    'Instantcheckmate': { method: 'form',  url: 'https://www.instantcheckmate.com/opt-out/',
      steps: ['Go to opt-out page', 'Search your listing', 'Submit opt-out'] },
    'Canada411':        { method: 'form',  url: 'https://www.canada411.ca/search/rr.html',
      steps: ['Go to removal page', 'Enter your listing number', 'Submit removal request'] },
    'Radaris Canada':   { method: 'form',  url: 'https://ca.radaris.com/control/privacy',
      steps: ['Create free account', 'Claim your profile', 'Request removal'] },
  };

  // ── Regions ────────────────────────────────────────────────────────
  readonly canadianProvinces = [
    { code: 'AB', name: 'Alberta' },
    { code: 'BC', name: 'British Columbia' },
    { code: 'MB', name: 'Manitoba' },
    { code: 'NB', name: 'New Brunswick' },
    { code: 'NL', name: 'Newfoundland' },
    { code: 'NS', name: 'Nova Scotia' },
    { code: 'NT', name: 'Northwest Territories' },
    { code: 'NU', name: 'Nunavut' },
    { code: 'ON', name: 'Ontario' },
    { code: 'PE', name: 'Prince Edward Island' },
    { code: 'QC', name: 'Quebec' },
    { code: 'SK', name: 'Saskatchewan' },
    { code: 'YT', name: 'Yukon' },
  ];

  readonly usStates = [
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA',
    'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
    'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
    'VA','WA','WV','WI','WY'
  ];

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    // Small delay ensures Angular is fully bootstrapped before
    // the health check runs — prevents SSG pre-render from
    // showing the offline state permanently
    setTimeout(() => this.checkApiHealth(), 300);
  }

  // ── API health check ───────────────────────────────────────────────
  checkApiHealth(): void {
    this.http.get<any>(`${this.API}/health`, {
      headers: { 'Cache-Control': 'no-cache' }
    }).subscribe({
      next: () => {
        this.apiConnected = true;
        this.loadStats();
        // Re-check every 30s to detect if API goes offline later
        setTimeout(() => this.checkApiHealth(), 30000);
      },
      error: () => {
        this.apiConnected = false;
        // Retry every 5s when offline
        setTimeout(() => this.checkApiHealth(), 5000);
      }
    });
  }

  loadStats(): void {
    this.http.get<any>(`${this.API}/stats`).subscribe({
      next: data => this.dbStats = data,
      error: err  => console.error('Stats error:', err),
    });
  }

  // ── Scan ───────────────────────────────────────────────────────────
  startScan(): void {
    if (!this.form.firstName || !this.form.lastName) {
      alert('Please enter at least your first and last name.');
      return;
    }
    if (!this.apiConnected) {
      alert('API is not running. Start it with: node server.js');
      return;
    }

    this.isScanning     = true;
    this.scanComplete   = false;
    this.notFound       = false;
    this.scanResult     = null;
    this.selectedRecord = null;
    this.automationLog  = [];
    this.stepState      = ['idle','idle','idle','idle'];
    this.progressPct    = 0;

    // Fire the real API request immediately — don't wait for animation
    this.fetchExposureData();

    // Run the progress animation in parallel — purely cosmetic
    const steps = [
      { label: 'Connecting to database…',     pct: 20 },
      { label: 'Searching US broker sites…',  pct: 45 },
      { label: 'Searching Canadian brokers…', pct: 70 },
      { label: 'Building exposure report…',   pct: 90 },
    ];

    let i = 0;
    const tick = () => {
      if (i > 0) this.stepState[i - 1] = 'done';
      if (i >= steps.length) return; // stop — buildReport() will set scanComplete
      this.stepState[i]  = 'active';
      this.progressLabel = steps[i].label;
      this.progressPct   = steps[i].pct;
      i++;
      setTimeout(tick, 700);
    };
    tick();
  }

  private fetchExposureData(): void {
    const fullName = `${this.form.firstName} ${this.form.lastName}`.trim();
    let params = new HttpParams()
      .set('q',     fullName)
      .set('limit', '200');

    if (this.form.city)     params = params.set('city',  this.form.city);
    if (this.form.province) params = params.set('state', this.form.province);

    this.http.get<any>(`${this.API}/search/exposure`, { params }).subscribe({
      next:  data  => this.buildReport(data),
      error: err   => {
        this.isScanning = false;
        this.stepState  = ['idle','idle','idle','idle'];
        alert(`Scan failed: ${err.status === 0
          ? 'API not reachable — is node server.js running?'
          : err.message}`);
      }
    });
  }

  private buildReport(data: any): void {
    // Reset animation state
    this.stepState = ['idle','idle','idle','idle'];

    if (!data.results || data.results.length === 0) {
      // Set notFound BEFORE turning off isScanning so Angular
      // renders the not-found panel in the same change detection tick
      this.notFound    = true;
      this.notFoundMsg = data.message || 'No records found for this name.';
      this.scanResult  = null;
      this.isScanning  = false;
      this.scanComplete = true;
      return;
    }

    // Add opt-out status and config to each record
    const records: ExposureRecord[] = data.results.map((r: any) => ({
      ...r,
      opt_out_url:    this.optOutConfig[r.broker_name]?.url || r.opt_out_url || '',
      opt_out_status: 'pending' as const,
      first_seen:     this.formatDate(r.first_seen),
      last_confirmed: this.formatDate(r.last_confirmed),
    }));

    // Set scanResult FIRST so the results panel has data when it appears,
    // then flip isScanning off — both happen in the same change detection cycle
    this.scanResult = {
      total_found:   data.count,
      brokers_found: new Set(records.map((r: ExposureRecord) => r.broker_name)).size,
      records,
      not_found:     false,
    };
    this.notFound     = false;
    this.isScanning   = false;
    this.scanComplete = true;
  }

  // ── Opt-out methods ────────────────────────────────────────────────
  openOptOutLink(record: ExposureRecord): void {
    const url = record.listing_url || record.opt_out_url;
    if (url) {
      window.open(url, '_blank');
      record.opt_out_status = 'opened';
    }
  }

  openOptOutPage(record: ExposureRecord): void {
    const url = record.opt_out_url || this.optOutConfig[record.broker_name]?.url;
    if (url) {
      window.open(url, '_blank');
      record.opt_out_status = 'opened';
    }
  }

  startAutomation(record: ExposureRecord): void {
    this.selectedRecord   = record;
    this.automationRunning = true;
    this.automationLog    = [];
    record.opt_out_status = 'automated';

    const config = this.optOutConfig[record.broker_name];
    if (!config) {
      this.automationLog.push('⚠ No automation config for this broker.');
      this.automationLog.push('Opening opt-out page manually instead...');
      this.openOptOutPage(record);
      this.automationRunning = false;
      return;
    }

    const steps = config.steps || ['Opening opt-out page...'];
    let i = 0;

    const runStep = () => {
      if (i >= steps.length) {
        this.automationLog.push('✓ All steps complete — opening opt-out page now.');
        this.automationLog.push('⚠ Complete the final submission on the page that opens.');
        window.open(config.url, '_blank');
        this.automationRunning = false;
        record.opt_out_status  = 'done';
        return;
      }
      this.automationLog.push(`→ Step ${i + 1}: ${steps[i]}`);
      i++;
      setTimeout(runStep, 800);
    };

    this.automationLog.push(`Starting opt-out for ${record.broker_name}...`);
    this.automationLog.push(`Method: ${config.method}`);
    this.automationLog.push('─────────────────────────');
    setTimeout(runStep, 500);
  }

  closeAutomation(): void {
    this.automationRunning = false;
    this.selectedRecord    = null;
    this.automationLog     = [];
  }

  // ── Opt-out all ────────────────────────────────────────────────────
  optOutAll(): void {
    if (!this.scanResult) return;
    const pending = this.scanResult.records.filter(r => r.opt_out_status === 'pending');
    pending.forEach((record, i) => {
      setTimeout(() => {
        const url = record.opt_out_url || this.optOutConfig[record.broker_name]?.url;
        if (url) {
          window.open(url, '_blank');
          record.opt_out_status = 'opened';
        }
      }, i * 1000); // stagger 1 second apart to avoid popup blocker
    });
  }

  // ── Helpers ────────────────────────────────────────────────────────
  get riskLevel(): 'low' | 'medium' | 'high' | 'critical' {
    const n = this.scanResult?.brokers_found || 0;
    if (n === 0) return 'low';
    if (n <= 2)  return 'medium';
    if (n <= 5)  return 'high';
    return 'critical';
  }

  get riskLabel(): string {
    return { low:'Low Exposure', medium:'Medium Exposure',
             high:'High Exposure', critical:'Critical Exposure' }[this.riskLevel];
  }

  get riskColor(): string {
    return { low:'var(--accent3)', medium:'var(--warning)',
             high:'var(--danger)', critical:'#ff0055' }[this.riskLevel];
  }

  getStatusIcon(status: string): string {
    return { pending:'⏳', opened:'🔗', automated:'🤖', done:'✅' }[status] || '⏳';
  }

  getStatusLabel(status: string): string {
    return { pending:'Not started', opened:'Opt-out opened',
             automated:'Auto submitted', done:'Complete' }[status] || 'Pending';
  }

  getBrokerFlag(country: string): string {
    return country === 'CA' ? '🇨🇦' : '🇺🇸';
  }

  private formatDate(dateStr: string): string {
    if (!dateStr) return '';
    try { return new Date(dateStr).toLocaleDateString(); }
    catch { return dateStr; }
  }

  resetScan(): void {
    this.scanComplete   = false;
    this.notFound       = false;
    this.notFoundMsg    = '';
    this.scanResult     = null;
    this.selectedRecord = null;
    this.automationLog  = [];
    this.isScanning     = false;
    this.progressPct    = 0;
    this.progressLabel  = '';
    this.stepState      = ['idle','idle','idle','idle'];
    this.form = { firstName:'', lastName:'', city:'',
                  province:'', age:'', phone:'', email:'' };
  }

  get pendingCount(): number {
    return this.scanResult?.records.filter(r => r.opt_out_status === 'pending').length || 0;
  }

  get doneCount(): number {
    return this.scanResult?.records.filter(
      r => r.opt_out_status === 'done' || r.opt_out_status === 'opened'
    ).length || 0;
  }
}
