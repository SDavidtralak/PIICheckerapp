import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

// ── Interfaces ─────────────────────────────────────────────────────────
interface ReportRow {
  [key: string]: string | number | boolean;
}

interface TableConfig {
  cols: string[];
  fields: string[];
  statusField?: string;
  statuses?: string[];
}

interface Stats {
  total: number;
  active: number;
  pending: number;
  flagged: number;
  label3: string;
  label4: string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrls: ['./app.css']
})
export class AppComponent implements OnInit {

  // ── Form fields ────────────────────────────────────────────────────
  searchTerm    = '';
  dbTable       = '';
  filterStatus  = 'all';
  dateFrom      = '';
  dateTo        = '';
  notes         = '';
  incSummary    = true;
  incTable      = true;
  incCharts     = false;
  incNotes      = false;

  // ── Query preview ──────────────────────────────────────────────────
  queryPreview  = '';

  // ── Progress state ─────────────────────────────────────────────────
  isLoading     = false;
  progressLabel = '';
  progressPct   = 0;
  stepState: ('idle' | 'active' | 'done')[] = ['idle', 'idle', 'idle', 'idle'];

  // ── Report state ───────────────────────────────────────────────────
  reportVisible   = false;
  reportTime      = '';
  reportRows      = 0;
  stats: Stats    = { total: 0, active: 0, pending: 0, flagged: 0, label3: 'Pending', label4: 'Flagged' };
  tableCols: string[]     = [];
  reportData: ReportRow[] = [];
  sortCol = 0;
  sortAsc = true;

  // ── Dynamic status options per table ──────────────────────────────
  statusOptions: string[] = [];

  // ── Table definitions matching schema.sql ─────────────────────────
  private readonly tableConfigs: Record<string, TableConfig> = {
    users: {
      cols:   ['ID', 'Email', 'Full Name', 'Brokers Found', 'Active Exposures', 'Created At'],
      fields: ['id', 'email', 'full_name', 'brokers_with_data', 'active_exposures', 'created_at'],
    },
    user_pii_profiles: {
      cols:   ['ID', 'User ID', 'First Name', 'Last Name', 'City', 'State', 'Country'],
      fields: ['id', 'user_id', 'first_name', 'last_name', 'city', 'state', 'country'],
    },
    brokers: {
      cols:        ['ID', 'Name', 'Category', 'Opt-Out URL', 'Active', 'Created At'],
      fields:      ['id', 'name', 'category', 'opt_out_url', 'is_active', 'created_at'],
      statusField: 'category',
      statuses:    ['people_search', 'marketing', 'credit_reporting', 'background_check', 'social_aggregator', 'other'],
    },
    scan_jobs: {
      cols:        ['ID', 'User ID', 'Status', 'Started At', 'Completed At', 'Created At'],
      fields:      ['id', 'user_id', 'status', 'started_at', 'completed_at', 'created_at'],
      statusField: 'status',
      statuses:    ['queued', 'running', 'completed', 'failed'],
    },
    broker_findings: {
      cols:        ['ID', 'User ID', 'Broker ID', 'Confidence Score', 'Removed', 'First Seen'],
      fields:      ['id', 'user_id', 'broker_id', 'confidence_score', 'is_removed', 'first_seen_at'],
      statusField: 'is_removed',
      statuses:    ['false', 'true'],
    },
    finding_pii_categories: {
      cols:   ['Finding ID', 'PII Category ID', 'Category Name', 'Description', 'Broker', 'Scan Job'],
      fields: ['finding_id', 'pii_category_id', 'category_name', 'description', 'broker', 'scan_job'],
    },
    v_user_exposure_summary: {
      cols:   ['User ID', 'Email', 'Full Name', 'Brokers With Data', 'Active Exposures', 'Last Seen'],
      fields: ['user_id', 'email', 'full_name', 'brokers_with_data', 'active_exposures', 'last_seen_at'],
    },
    v_user_broker_findings: {
      cols:   ['User ID', 'Broker Name', 'Category', 'Confidence', 'PII Found', 'First Seen'],
      fields: ['user_id', 'broker_name', 'broker_category', 'confidence_score', 'pii_categories_found', 'first_seen_at'],
    },
  };

  // ── Mock seed data ─────────────────────────────────────────────────
  private readonly mockEmails  = ['alice@email.com', 'bob@domain.net', 'carol@webmail.org', 'dan@inbox.io', 'eve@mail.co'];
  private readonly mockNames   = ['Alice Johnson', 'Bob Martinez', 'Carol White', 'Dan Brown', 'Eve Davis'];
  private readonly mockBrokers = ['Spokeo', 'BeenVerified', 'Whitepages', 'Intelius', 'MyLife', 'PeopleFinder'];
  private readonly mockCities  = ['Austin', 'New York', 'Chicago', 'Los Angeles', 'Seattle'];
  private readonly mockStates  = ['TX', 'NY', 'IL', 'CA', 'WA'];
  private readonly brokerCats  = ['people_search', 'marketing', 'credit_reporting', 'background_check', 'social_aggregator', 'other'];
  private readonly piiCats     = ['full_name', 'email', 'phone', 'home_address', 'date_of_birth', 'relatives', 'social_profiles', 'employment'];

  private rand(arr: string[])              { return arr[Math.floor(Math.random() * arr.length)]; }
  private randInt(min: number, max: number){ return Math.floor(Math.random() * (max - min + 1)) + min; }
  private randDate()                       { return new Date(Date.now() - Math.random() * 1e10).toISOString().split('T')[0]; }
  private randId()                         { return String(this.randInt(1000, 9999)); }

  ngOnInit(): void {
    const today = new Date().toISOString().split('T')[0];
    const past  = new Date(Date.now() - 30 * 864e5).toISOString().split('T')[0];
    this.dateTo   = today;
    this.dateFrom = past;
  }

  // ── Table change → update status dropdown ─────────────────────────
  onTableChange(): void {
    const cfg          = this.tableConfigs[this.dbTable];
    this.statusOptions = cfg?.statuses ?? [];
    this.filterStatus  = 'all';
    this.updatePreview();
  }

  // ── Live query preview ─────────────────────────────────────────────
  updatePreview(): void {
    if (!this.dbTable) { this.queryPreview = ''; return; }

    const cfg = this.tableConfigs[this.dbTable];
    const sf  = cfg?.statusField ?? 'status';
    let q     = `SELECT * FROM ${this.dbTable}`;
    const where: string[] = [];

    if (this.searchTerm) {
      if (['users', 'v_user_exposure_summary'].includes(this.dbTable))
        where.push(`(email LIKE '%${this.searchTerm}%' OR full_name LIKE '%${this.searchTerm}%')`);
      else if (this.dbTable === 'brokers')
        where.push(`(name LIKE '%${this.searchTerm}%' OR website_url LIKE '%${this.searchTerm}%')`);
      else if (['broker_findings', 'v_user_broker_findings'].includes(this.dbTable))
        where.push(`(user_id = '${this.searchTerm}' OR broker_id = '${this.searchTerm}')`);
      else
        where.push(`user_id = '${this.searchTerm}'`);
    }

    if (this.filterStatus !== 'all') where.push(`${sf} = '${this.filterStatus}'`);
    if (this.dateFrom) where.push(`created_at >= '${this.dateFrom}'`);
    if (this.dateTo)   where.push(`created_at <= '${this.dateTo}'`);
    if (where.length)  q += `\nWHERE ${where.join('\n  AND ')}`;
    q += `\nORDER BY id DESC\nLIMIT 500;`;
    this.queryPreview = q;
  }

  // ── Run search ─────────────────────────────────────────────────────
  runSearch(): void {
    if (!this.dbTable) { alert('Please select a database table or view.'); return; }

    this.isLoading     = true;
    this.reportVisible = false;
    this.stepState     = ['idle', 'idle', 'idle', 'idle'];
    this.progressPct   = 0;

    const steps = [
      { label: 'Connecting to database…', pct: 20 },
      { label: 'Executing query…',        pct: 50 },
      { label: 'Processing results…',     pct: 80 },
      { label: 'Rendering report…',       pct: 100 },
    ];

    let i = 0;
    const tick = () => {
      if (i > 0) this.stepState[i - 1] = 'done';
      if (i >= steps.length) {
        this.renderReport();
        this.isLoading = false;
        this.stepState = ['idle', 'idle', 'idle', 'idle'];
        return;
      }
      this.stepState[i]  = 'active';
      this.progressLabel = steps[i].label;
      this.progressPct   = steps[i].pct;
      i++;
      setTimeout(tick, 600);
    };
    tick();
  }

  // ── Render report ──────────────────────────────────────────────────
  private renderReport(): void {
    const count        = this.randInt(15, 50);
    const cfg          = this.tableConfigs[this.dbTable];
    this.tableCols     = cfg.cols;
    this.reportData    = this.generateRows(this.dbTable, count);

    switch (this.dbTable) {
      case 'scan_jobs':
        this.stats = {
          total:   count,
          active:  this.reportData.filter(r => r['status'] === 'completed').length,
          pending: this.reportData.filter(r => r['status'] === 'queued' || r['status'] === 'running').length,
          flagged: this.reportData.filter(r => r['status'] === 'failed').length,
          label3: 'Queued/Running', label4: 'Failed'
        };
        break;
      case 'broker_findings':
      case 'v_user_broker_findings':
        this.stats = {
          total:   count,
          active:  this.reportData.filter(r => r['is_removed'] === 'false').length,
          pending: this.randInt(1, 5),
          flagged: this.reportData.filter(r => r['is_removed'] === 'true').length,
          label3: 'Pending Removal', label4: 'Removed'
        };
        break;
      case 'brokers':
        this.stats = {
          total:   count,
          active:  this.reportData.filter(r => r['is_active'] === 'true').length,
          pending: this.reportData.filter(r => r['category'] === 'people_search').length,
          flagged: this.reportData.filter(r => r['category'] === 'credit_reporting').length,
          label3: 'People Search', label4: 'Credit Reporting'
        };
        break;
      case 'v_user_exposure_summary':
        this.stats = {
          total:   count,
          active:  this.reportData.reduce((s, r) => s + Number(r['active_exposures']), 0),
          pending: this.randInt(1, 8),
          flagged: this.randInt(0, 4),
          label3: 'Pending Opt-Outs', label4: 'High Risk'
        };
        break;
      default:
        this.stats = {
          total: count, active: this.randInt(5, count), pending: this.randInt(1, 8), flagged: this.randInt(0, 4),
          label3: 'Pending', label4: 'Flagged'
        };
    }

    this.reportTime    = new Date().toLocaleTimeString();
    this.reportRows    = count;
    this.sortCol       = 0;
    this.sortAsc       = true;
    this.reportVisible = true;
  }

  // ── Mock row generator ─────────────────────────────────────────────
  private generateRows(table: string, count: number): ReportRow[] {
    return Array.from({ length: count }, (_, i) => this.generateRow(table, i));
  }

  private generateRow(table: string, i: number): ReportRow {
    const id = String(i + 1);
    switch (table) {
      case 'users':
        return { id, email: this.rand(this.mockEmails), full_name: this.rand(this.mockNames),
                 brokers_with_data: this.randInt(1, 12), active_exposures: this.randInt(0, 10), created_at: this.randDate() };
      case 'user_pii_profiles':
        return { id, user_id: this.randId(), first_name: this.rand(['Alice','Bob','Carol','Dan','Eve']),
                 last_name: this.rand(['Johnson','Martinez','White','Brown','Davis']),
                 city: this.rand(this.mockCities), state: this.rand(this.mockStates), country: 'US' };
      case 'brokers':
        return { id, name: this.rand(this.mockBrokers), category: this.rand(this.brokerCats),
                 opt_out_url: 'https://optout.example.com',
                 is_active: Math.random() > 0.2 ? 'true' : 'false', created_at: this.randDate() };
      case 'scan_jobs':
        return { id, user_id: this.randId(),
                 status: this.rand(['queued','running','completed','completed','completed','failed']),
                 started_at: this.randDate(), completed_at: this.randDate(), created_at: this.randDate() };
      case 'broker_findings':
        return { id, user_id: this.randId(), broker_id: this.randId(),
                 confidence_score: this.randInt(60, 100),
                 is_removed: Math.random() > 0.7 ? 'true' : 'false',
                 first_seen_at: this.randDate() };
      case 'finding_pii_categories':
        return { finding_id: this.randId(), pii_category_id: this.randId(),
                 category_name: this.rand(this.piiCats), description: 'PII data found on broker',
                 broker: this.rand(this.mockBrokers), scan_job: this.randId() };
      case 'v_user_exposure_summary':
        return { user_id: id, email: this.rand(this.mockEmails), full_name: this.rand(this.mockNames),
                 brokers_with_data: this.randInt(1, 15), active_exposures: this.randInt(0, 12),
                 last_seen_at: this.randDate() };
      case 'v_user_broker_findings':
        return { user_id: this.randId(), broker_name: this.rand(this.mockBrokers),
                 broker_category: this.rand(this.brokerCats), confidence_score: this.randInt(60, 100),
                 pii_categories_found: this.rand(this.piiCats) + ', ' + this.rand(this.piiCats),
                 first_seen_at: this.randDate() };
      default:
        return { id };
    }
  }

  // ── Sort ───────────────────────────────────────────────────────────
  sortTable(col: number): void {
    if (this.sortCol === col) { this.sortAsc = !this.sortAsc; }
    else { this.sortCol = col; this.sortAsc = true; }
    const cfg = this.tableConfigs[this.dbTable];
    const key = cfg?.fields[col] ?? 'id';
    this.reportData = [...this.reportData].sort((a, b) => {
      const av = String(a[key] ?? '');
      const bv = String(b[key] ?? '');
      return this.sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
    });
  }

  // ── Badge helpers ──────────────────────────────────────────────────
  getBadgeClass(value: string, field: string): string {
    if (field === 'status')
      return ({ completed:'badge-green', running:'badge-blue', queued:'badge-yellow', failed:'badge-red' } as Record<string,string>)[value] ?? 'badge-blue';
    if (field === 'is_removed')
      return value === 'true' ? 'badge-red' : 'badge-green';
    if (field === 'is_active')
      return value === 'true' ? 'badge-green' : 'badge-red';
    if (field === 'category' || field === 'broker_category')
      return ({ people_search:'badge-blue', marketing:'badge-yellow', credit_reporting:'badge-red',
                background_check:'badge-blue', social_aggregator:'badge-green', other:'badge-muted' } as Record<string,string>)[value] ?? 'badge-blue';
    return 'badge-blue';
  }

  isBadgeField(field: string): boolean {
    return ['status', 'is_removed', 'is_active', 'category', 'broker_category'].includes(field);
  }

  getFieldKey(col: number): string {
    return this.tableConfigs[this.dbTable]?.fields[col] ?? '';
  }

  // ── Export ─────────────────────────────────────────────────────────
  exportCSV(): void {
    if (!this.reportData.length) return;
    const cfg    = this.tableConfigs[this.dbTable];
    const header = cfg.fields.join(',');
    const rows   = this.reportData.map(r => cfg.fields.map(f => r[f] ?? '').join(','));
    this.download('report.csv', [header, ...rows].join('\n'), 'text/csv');
  }

  exportJSON(): void {
    if (!this.reportData.length) return;
    this.download('report.json', JSON.stringify(this.reportData, null, 2), 'application/json');
  }

  private download(filename: string, content: string, type: string): void {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([content], { type }));
    a.download = filename;
    a.click();
  }

  printReport(): void { window.print(); }

  // ── Reset ──────────────────────────────────────────────────────────
  resetForm(): void {
    this.searchTerm    = '';
    this.dbTable       = '';
    this.filterStatus  = 'all';
    this.notes         = '';
    this.incSummary    = true;
    this.incTable      = true;
    this.incCharts     = false;
    this.incNotes      = false;
    this.reportVisible = false;
    this.queryPreview  = '';
    this.statusOptions = [];
    const today = new Date().toISOString().split('T')[0];
    const past  = new Date(Date.now() - 30 * 864e5).toISOString().split('T')[0];
    this.dateTo   = today;
    this.dateFrom = past;
  }
}
