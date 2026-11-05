// The operator's report the agent made in the chat (CUSTOM "report"): a PDF of one design, to
// download. The server builds it from the conversation (GET /api/report.pdf); nothing is made here.

import type { ReportView } from "../agent/types";

export function ReportCard({ value }: { value: ReportView }) {
  return (
    <section className="card report-card ta-rise" aria-label={`Operator's report of ${value.id}`}>
      <div className="report-card-head">
        <span className="report-card-icon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 16 16">
            <path d="M4 1.8h5.4L12.5 5v9.2H4z" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
            <path d="M9.2 2v3.2h3.2" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
            <text x="8.2" y="11.6" fontSize="3.4" textAnchor="middle" fill="currentColor" fontWeight="700">
              PDF
            </text>
          </svg>
        </span>
        <div className="report-card-title">
          <strong>Operator&apos;s report</strong>
          <span>
            <span className="chip">{value.id}</span> {value.pages} A4 pages · {value.kb} kB
          </span>
        </div>
        <a className="report-card-download ta-btn ta-ink" href={value.url} download={value.file} title={`Download ${value.file}`}>
          <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M8 2.5v7.2M5 6.9l3 3 3-3M3 12.8h10" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Download PDF
        </a>
      </div>
      <ol className="report-card-sections">
        {value.sections.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ol>
    </section>
  );
}
