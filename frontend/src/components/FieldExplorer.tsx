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
      <div className="rankings-controls" style={{ display: "flex", gap: "16px", flexWrap: "wrap", alignItems: "center", marginBottom: "20px" }}>
        <div style={{ flex: "1 1 240px" }}>
          <input
            type="search"
            placeholder={`Filter ${occupations.length} ${fieldName} careers...`}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input"
            style={{ width: "100%", padding: "10px 14px", borderRadius: "var(--radius-xs)", border: "1px solid var(--line)" }}
            aria-label={`Filter ${fieldName} careers`}
          />
        </div>

        <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--muted)" }}>Filter by risk:</span>
          <select
            value={filterRiskBand}
            onChange={(e) => setFilterRiskBand(e.target.value)}
            className="select"
            style={{ padding: "8px 12px", borderRadius: "var(--radius-xs)", border: "1px solid var(--line)", background: "white", fontSize: "0.88rem" }}
            aria-label="Filter by replacement risk band"
          >
            <option value="all">All Risk Bands</option>
            <option value="high">High Risk (67–100)</option>
            <option value="moderate">Moderate Risk (34–66)</option>
            <option value="low">Low Risk (0–33)</option>
          </select>
        </div>
      </div>

      <div className="rankings-table-wrap">
        <table className="rankings-table">
          <thead>
            <tr>
              <th scope="col" style={{ width: "60px", textAlign: "center" }}>#</th>
              <th scope="col">
                <button
                  type="button"
                  onClick={() => handleSort("title")}
                  style={{ background: "none", border: "none", font: "inherit", fontWeight: 800, cursor: "pointer", color: "inherit", display: "inline-flex", alignItems: "center", gap: "4px" }}
                >
                  Occupation {sortBy === "title" ? (sortOrder === "desc" ? "↓" : "↑") : ""}
                </button>
              </th>
              <th scope="col" style={{ textAlign: "center" }}>
                <button
                  type="button"
                  onClick={() => handleSort("replacementRisk")}
                  style={{ background: "none", border: "none", font: "inherit", fontWeight: 800, cursor: "pointer", color: "inherit", display: "inline-flex", alignItems: "center", gap: "4px" }}
                >
                  Replacement Risk {sortBy === "replacementRisk" ? (sortOrder === "desc" ? "↓" : "↑") : ""}
                </button>
              </th>
              <th scope="col" style={{ textAlign: "center" }}>
                <button
                  type="button"
                  onClick={() => handleSort("aiExposure")}
                  style={{ background: "none", border: "none", font: "inherit", fontWeight: 800, cursor: "pointer", color: "inherit", display: "inline-flex", alignItems: "center", gap: "4px" }}
                >
                  AI Exposure {sortBy === "aiExposure" ? (sortOrder === "desc" ? "↓" : "↑") : ""}
                </button>
              </th>
              <th scope="col" style={{ textAlign: "right" }}>Analysis</th>
            </tr>
          </thead>
          <tbody>
            {filteredAndSorted.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ textAlign: "center", padding: "32px", color: "var(--muted)" }}>
                  No verified occupations match your filter criteria.
                </td>
              </tr>
            ) : (
              filteredAndSorted.map((job, idx) => {
                const riskSem = getScoreSemantics("replacement_risk", job.replacementRisk);
                const expSem = getScoreSemantics("ai_exposure", job.aiExposure);
                return (
                  <tr key={job.slug}>
                    <td style={{ textAlign: "center", color: "var(--muted)", fontWeight: 700 }}>
                      {idx + 1}
                    </td>
                    <td>
                      <Link href={`/jobs/${job.slug}`} style={{ fontWeight: 700, color: "var(--ink)", textDecoration: "none" }}>
                        {job.title}
                      </Link>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span className={`score-badge ${riskSem.tone}`} title={riskSem.label}>
                        {Math.round(job.replacementRisk)}
                      </span>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span className={`score-badge ${expSem.tone}`} title={expSem.label}>
                        {Math.round(job.aiExposure)}
                      </span>
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <Link href={`/jobs/${job.slug}`} className="button secondary small" style={{ fontSize: "0.8rem", padding: "4px 10px" }}>
                        View →
                      </Link>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: "12px", fontSize: "0.82rem", color: "var(--muted)", textAlign: "right" }}>
        Showing {filteredAndSorted.length} of {occupations.length} verified {fieldName} occupations
      </div>
    </div>
  );
}
