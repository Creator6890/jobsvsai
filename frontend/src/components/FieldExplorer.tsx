"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { RankingOccupation } from "@/lib/api";
import { getScoreSemantics } from "@/lib/scoreSemantics";

interface FieldExplorerProps {
  occupations: RankingOccupation[];
  fieldName: string;
}

type SortField = "replacementRisk" | "aiExposure" | "title";
type SortOrder = "asc" | "desc";

export function FieldExplorer({ occupations, fieldName }: FieldExplorerProps) {
  const [sortBy, setSortBy] = useState<SortField>("replacementRisk");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [filterRiskBand, setFilterRiskBand] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const filteredAndSorted = useMemo(() => {
    let list = [...occupations];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter((j) => j.title.toLowerCase().includes(q));
    }

    if (filterRiskBand !== "all") {
      list = list.filter((j) => {
        const sem = getScoreSemantics("replacement_risk", j.replacementRisk);
        return sem.band === filterRiskBand;
      });
    }

    list.sort((a, b) => {
      let comparison = 0;
      if (sortBy === "title") {
        comparison = a.title.localeCompare(b.title);
      } else if (sortBy === "aiExposure") {
        comparison = a.aiExposure - b.aiExposure;
      } else {
        comparison = a.replacementRisk - b.replacementRisk;
      }
      return sortOrder === "desc" ? -comparison : comparison;
    });

    return list;
  }, [occupations, sortBy, sortOrder, filterRiskBand, searchQuery]);

  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "desc" ? "asc" : "desc");
    } else {
      setSortBy(field);
      setSortOrder(field === "title" ? "asc" : "desc");
    }
  };

  return (
    <div className="field-explorer">
      {/* Search and Filters */}
      <div
        className="field-controls"
        style={{
          display: "flex",
          gap: "16px",
          flexWrap: "wrap",
          alignItems: "center",
          marginBottom: "20px",
        }}
      >
        <div style={{ flex: "1 1 240px" }}>
          <input
            type="search"
            placeholder={`Filter ${occupations.length} ${fieldName} careers...`}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input"
            style={{
              width: "100%",
              padding: "10px 14px",
              borderRadius: "var(--radius-xs)",
              border: "1px solid var(--line)",
              background: "white",
              fontSize: "0.9rem",
            }}
            aria-label={`Filter ${fieldName} careers`}
          />
        </div>

        <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--muted)" }}>Filter by risk:</span>
          <select
            value={filterRiskBand}
            onChange={(e) => setFilterRiskBand(e.target.value)}
            className="select"
            style={{
              padding: "8px 12px",
              borderRadius: "var(--radius-xs)",
              border: "1px solid var(--line)",
              background: "white",
              fontSize: "0.88rem",
            }}
            aria-label="Filter by replacement risk band"
          >
            <option value="all">All Risk Bands</option>
            <option value="high">High Risk (67–100)</option>
            <option value="moderate">Moderate Risk (34–66)</option>
            <option value="low">Low Risk (0–33)</option>
          </select>
        </div>
      </div>

      {/* Shared Responsive Rankings Table */}
      <div className="card ranking-table">
        <div className="ranking-row ranking-header">
          <span className="ranking-col-rank">#</span>
          <span className="ranking-col-title">
            <button
              type="button"
              onClick={() => handleSort("title")}
              style={{
                background: "none",
                border: "none",
                font: "inherit",
                fontWeight: "inherit",
                color: "inherit",
                cursor: "pointer",
                padding: 0,
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              Occupation {sortBy === "title" ? (sortOrder === "desc" ? "↓" : "↑") : ""}
            </button>
          </span>
          <span className="ranking-col-cat">Domain</span>
          <span className="ranking-col-risk">
            <button
              type="button"
              onClick={() => handleSort("replacementRisk")}
              style={{
                background: "none",
                border: "none",
                font: "inherit",
                fontWeight: "inherit",
                color: "inherit",
                cursor: "pointer",
                padding: 0,
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              Replacement Risk {sortBy === "replacementRisk" ? (sortOrder === "desc" ? "↓" : "↑") : ""}
            </button>
          </span>
          <span className="ranking-col-exp">
            <button
              type="button"
              onClick={() => handleSort("aiExposure")}
              style={{
                background: "none",
                border: "none",
                font: "inherit",
                fontWeight: "inherit",
                color: "inherit",
                cursor: "pointer",
                padding: 0,
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              AI Exposure {sortBy === "aiExposure" ? (sortOrder === "desc" ? "↓" : "↑") : ""}
            </button>
          </span>
          <span className="ranking-col-action"></span>
        </div>

        {filteredAndSorted.map((job, index) => {
          const riskSem = getScoreSemantics("replacement_risk", job.replacementRisk);
          const expSem = getScoreSemantics("ai_exposure", job.aiExposure);

          return (
            <div className="ranking-row" key={job.slug}>
              <strong className="rank-number ranking-col-rank">{index + 1}</strong>
              <div className="ranking-col-title">
                <Link
                  href={`/jobs/${job.slug}`}
                  style={{ color: "var(--ink)", textDecoration: "none", fontWeight: 700 }}
                >
                  {job.title}
                </Link>
                <span className="mobile-category">{fieldName}</span>
              </div>
              <span className="ranking-col-cat">{fieldName}</span>
              <div className="ranking-col-risk">
                <span className={riskSem.badgeClass} title={riskSem.label}>
                  {Math.round(job.replacementRisk)}
                </span>
              </div>
              <div className="ranking-col-exp">
                <span className={expSem.badgeClass} title={expSem.label}>
                  {Math.round(job.aiExposure)}
                </span>
              </div>
              <div className="ranking-col-action">
                <Link className="button secondary" href={`/jobs/${job.slug}`}>
                  View <span aria-hidden="true">→</span>
                </Link>
              </div>
            </div>
          );
        })}

        {filteredAndSorted.length === 0 && (
          <div className="empty-state" style={{ padding: "32px", textAlign: "center", color: "var(--muted)" }}>
            No verified occupations match your filter criteria.
          </div>
        )}
      </div>

      <div style={{ marginTop: "12px", fontSize: "0.82rem", color: "var(--muted)", textAlign: "right" }}>
        Showing {filteredAndSorted.length} of {occupations.length} verified {fieldName} occupations
      </div>
    </div>
  );
}
