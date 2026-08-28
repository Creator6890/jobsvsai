"use client";

import { useId, useMemo, useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getScoreSemantics } from "@/lib/scoreSemantics";
import { CANONICAL_CAREER_FIELDS, CareerFieldSlug } from "@/lib/careerFields";

export interface ExplorerOccupation {
  slug: string;
  title: string;
  category: string;
  fieldSlug: CareerFieldSlug;
  fieldName: string;
  aiExposure: number;
  replacementRisk: number;
  confidence?: number;
}

const FIELD_COLORS: Record<string, string> = {
  "business-finance": "#3b82f6",
  "technology-data": "#6366f1",
  "office-administration": "#64748b",
  "healthcare": "#06b6d4",
  "science-research": "#8b5cf6",
  "engineering": "#0284c7",
  "education": "#10b981",
  "community-social-services": "#14b8a6",
  "legal": "#d97706",
  "management": "#4f46e5",
  "sales": "#f59e0b",
  "creative-media": "#ec4899",
  "protective-services": "#ef4444",
  "food-hospitality": "#f97316",
  "personal-care-services": "#a855f7",
  "agriculture-environment": "#84cc16",
  "skilled-trades": "#78716c",
  "transportation": "#0ea5e9",
  "production": "#6b7280",
};

function getFieldColor(fieldSlug: string): string {
  return FIELD_COLORS[fieldSlug] || "#6366f1";
}

function getDynamicInterpretation(aiExposure: number, replacementRisk: number): string {
  if (aiExposure >= 60 && replacementRisk < 50) {
    return "High AI capability overlap, but human, regulatory, or physical moats significantly buffer replacement pressure.";
  }
  if (aiExposure >= 60 && replacementRisk >= 60) {
    return "High exposure coupled with high structural vulnerability across repetitive or routine digital workflows.";
  }
  if (aiExposure < 40 && replacementRisk < 40) {
    return "Low AI overlap; physical execution, unpredictable environments, or manual dexterity remain dominant.";
  }
  if (aiExposure < 50 && replacementRisk >= 50) {
    return "Moderate technical capability overlap with elevated structural vulnerability from commercial consolidation.";
  }
  return "Balanced profile where AI accelerates specific tasks while human supervision governs final outcomes.";
}

export function OccupationMapExplorer({
  occupations,
}: {
  occupations: ExplorerOccupation[];
}) {
  const router = useRouter();
  const searchInputId = useId();
  const fieldSelectId = useId();
  const riskSelectId = useId();
  const exposureSelectId = useId();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedField, setSelectedField] = useState<string>("all");
  const [selectedRiskBand, setSelectedRiskBand] = useState<string>("all");
  const [selectedExposureBand, setSelectedExposureBand] = useState<string>("all");
  const [hoveredJob, setHoveredJob] = useState<ExplorerOccupation | null>(null);
  const [selectedJob, setSelectedJob] = useState<ExplorerOccupation | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Filter occupations
  const filteredOccupations = useMemo(() => {
    return occupations.filter((job) => {
      // Field filter
      if (selectedField !== "all" && job.fieldSlug !== selectedField) {
        return false;
      }
      // Risk filter
      if (selectedRiskBand === "high" && job.replacementRisk < 67) return false;
      if (selectedRiskBand === "moderate" && (job.replacementRisk < 34 || job.replacementRisk > 66)) return false;
      if (selectedRiskBand === "low" && job.replacementRisk > 33) return false;

      // Exposure filter
      if (selectedExposureBand === "high" && job.aiExposure < 67) return false;
      if (selectedExposureBand === "moderate" && (job.aiExposure < 34 || job.aiExposure > 66)) return false;
      if (selectedExposureBand === "low" && job.aiExposure > 33) return false;

      return true;
    });
  }, [occupations, selectedField, selectedRiskBand, selectedExposureBand]);

  // Autocomplete search suggestions
  const searchSuggestions = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];
    return occupations
      .filter((j) => j.title.toLowerCase().includes(q) || j.slug.toLowerCase().includes(q))
      .slice(0, 6);
  }, [occupations, searchQuery]);

  // Highlighted matching jobs from search
  const searchMatchedSlugs = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return new Set<string>();
    return new Set(
      occupations
        .filter((j) => j.title.toLowerCase().includes(q) || j.slug.toLowerCase().includes(q))
        .map((j) => j.slug)
    );
  }, [occupations, searchQuery]);

  const hasActiveFilters =
    selectedField !== "all" ||
    selectedRiskBand !== "all" ||
    selectedExposureBand !== "all" ||
    searchQuery.trim().length > 0;

  const handleResetFilters = () => {
    setSelectedField("all");
    setSelectedRiskBand("all");
    setSelectedExposureBand("all");
    setSearchQuery("");
    setSelectedJob(null);
    setHoveredJob(null);
  };

  // SVG Dimension Constants
  const SVG_WIDTH = 800;
  const SVG_HEIGHT = 540;
  const PAD_LEFT = 60;
  const PAD_RIGHT = 30;
  const PAD_TOP = 30;
  const PAD_BOTTOM = 50;

  const PLOT_WIDTH = SVG_WIDTH - PAD_LEFT - PAD_RIGHT; // 710
  const PLOT_HEIGHT = SVG_HEIGHT - PAD_TOP - PAD_BOTTOM; // 460

  const getSvgX = (exposure: number) => PAD_LEFT + (Math.max(0, Math.min(100, exposure)) / 100) * PLOT_WIDTH;
  const getSvgY = (risk: number) => PAD_TOP + PLOT_HEIGHT - (Math.max(0, Math.min(100, risk)) / 100) * PLOT_HEIGHT;

  const handleDotClick = (job: ExplorerOccupation) => {
    setSelectedJob(job);
    if (typeof window !== "undefined" && window.innerWidth > 900) {
      router.push(`/jobs/${job.slug}`);
    }
  };

  const handleDotHover = (job: ExplorerOccupation, e: React.MouseEvent<SVGCircleElement>) => {
    setHoveredJob(job);
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const rawX = e.clientX - rect.left;
      const rawY = e.clientY - rect.top;
      const clampedX = Math.max(10, Math.min(rawX + 12, rect.width - 250));
      const clampedY = Math.max(10, rawY - 110);
      setTooltipPos({ x: clampedX, y: clampedY });
    }
  };

  const handleDotLeave = () => {
    setHoveredJob(null);
    setTooltipPos(null);
  };

  // Select job from search
  const handleSelectSearchJob = (job: ExplorerOccupation) => {
    setSelectedJob(job);
    setHoveredJob(job);
    setSearchQuery(job.title);
    setIsSearchFocused(false);
  };

  const activeJob = hoveredJob || selectedJob;

  return (
    <div className="map-explorer-wrapper" ref={containerRef}>
      {/* Controls & Filter Toolbar */}
      <div className="map-toolbar card">
        <div className="map-search-col">
          <label htmlFor={searchInputId} className="sr-only">
            Search occupations
          </label>
          <div className="map-search-input-wrap">
            <input
              id={searchInputId}
              type="search"
              className="input map-search-input"
              placeholder="Search occupation (e.g. Accountant, Software Developer)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => setIsSearchFocused(true)}
              onBlur={() => setTimeout(() => setIsSearchFocused(false), 250)}
              autoComplete="off"
            />
            {searchQuery && (
              <button
                type="button"
                className="map-search-clear"
                onClick={() => setSearchQuery("")}
                aria-label="Clear search"
              >
                ×
              </button>
            )}

            {/* Suggestions dropdown */}
            {(isSearchFocused || searchQuery.trim().length > 0) && searchSuggestions.length > 0 && (
              <ul className="map-search-dropdown" role="listbox">
                {searchSuggestions.map((job) => (
                  <li
                    key={job.slug}
                    role="option"
                    aria-selected={selectedJob?.slug === job.slug}
                    className="map-search-option"
                    onMouseDown={() => handleSelectSearchJob(job)}
                    onClick={() => handleSelectSearchJob(job)}
                  >
                    <span className="option-title">{job.title}</span>
                    <span className="option-meta">
                      Exp: {job.aiExposure} | Risk: {job.replacementRisk}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="map-filters-col">
          {/* Career Field Filter */}
          <div className="filter-select-group">
            <label htmlFor={fieldSelectId} className="filter-label">
              Field:
            </label>
            <select
              id={fieldSelectId}
              className="input select-input field-filter-select"
              value={selectedField}
              onChange={(e) => setSelectedField(e.target.value)}
            >
              <option value="all">All Fields ({occupations.length})</option>
              {Object.values(CANONICAL_CAREER_FIELDS).map((field) => (
                <option key={field.slug} value={field.slug}>
                  {field.name}
                </option>
              ))}
            </select>
          </div>

          {/* Risk Band Filter */}
          <div className="filter-select-group">
            <label htmlFor={riskSelectId} className="filter-label">
              Risk:
            </label>
            <select
              id={riskSelectId}
              className="input select-input risk-filter-select"
              value={selectedRiskBand}
              onChange={(e) => setSelectedRiskBand(e.target.value)}
            >
              <option value="all">All Risk</option>
              <option value="high">High Risk (67–100)</option>
              <option value="moderate">Moderate Risk (34–66)</option>
              <option value="low">Low Risk (0–33)</option>
            </select>
          </div>

          {/* Exposure Band Filter */}
          <div className="filter-select-group">
            <label htmlFor={exposureSelectId} className="filter-label">
              Exposure:
            </label>
            <select
              id={exposureSelectId}
              className="input select-input exposure-filter-select"
              value={selectedExposureBand}
              onChange={(e) => setSelectedExposureBand(e.target.value)}
            >
              <option value="all">All Exposure</option>
              <option value="high">High Exposure (67–100)</option>
              <option value="moderate">Moderate Exposure (34–66)</option>
              <option value="low">Low Exposure (0–33)</option>
            </select>
          </div>

          {/* Reset Action */}
          {hasActiveFilters && (
            <button
              type="button"
              className="button text-link reset-btn"
              onClick={handleResetFilters}
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Filter summary status */}
      <div className="map-status-bar">
        <span className="map-count">
          Showing <strong>{filteredOccupations.length}</strong> of {occupations.length} verified occupations
        </span>
        {hasActiveFilters && (
          <span className="muted small"> (Filtered dataset active)</span>
        )}
      </div>

      {/* Interactive 2D Scatter Chart */}
      <div className="map-chart-card card">
        <div className="map-svg-container">
          <svg
            viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
            className="map-svg"
            role="img"
            aria-label="2D Scatter plot comparing AI Exposure on the X-axis and Replacement Risk on the Y-axis across occupations"
          >
            <defs>
              {/* Drop shadow filter for active point */}
              <filter id="dot-shadow" x="-50%" y="-50%" width="200%" height="200%">
                <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.25" />
              </filter>
            </defs>

            {/* Quadrant Background Tints */}
            {/* Top-Right: High Exposure / High Risk */}
            <rect
              x={getSvgX(50)}
              y={getSvgY(100)}
              width={PLOT_WIDTH / 2}
              height={PLOT_HEIGHT / 2}
              fill="rgba(239, 68, 68, 0.035)"
              className="quadrant-rect"
            />
            {/* Bottom-Right: High Exposure / Lower Risk (Moat Zone) */}
            <rect
              x={getSvgX(50)}
              y={getSvgY(50)}
              width={PLOT_WIDTH / 2}
              height={PLOT_HEIGHT / 2}
              fill="rgba(99, 102, 241, 0.04)"
              className="quadrant-rect"
            />
            {/* Bottom-Left: Low Exposure / Low Risk */}
            <rect
              x={getSvgX(0)}
              y={getSvgY(50)}
              width={PLOT_WIDTH / 2}
              height={PLOT_HEIGHT / 2}
              fill="rgba(16, 185, 129, 0.035)"
              className="quadrant-rect"
            />
            {/* Top-Left: Low Exposure / Moderate-High Risk */}
            <rect
              x={getSvgX(0)}
              y={getSvgY(100)}
              width={PLOT_WIDTH / 2}
              height={PLOT_HEIGHT / 2}
              fill="rgba(245, 158, 11, 0.03)"
              className="quadrant-rect"
            />

            {/* Grid Lines & Axis Ticks */}
            {[0, 25, 50, 75, 100].map((val) => {
              const xPos = getSvgX(val);
              const yPos = getSvgY(val);
              return (
                <g key={`grid-${val}`}>
                  {/* Vertical Grid Line */}
                  <line
                    x1={xPos}
                    y1={PAD_TOP}
                    x2={xPos}
                    y2={PAD_TOP + PLOT_HEIGHT}
                    stroke={val === 50 ? "rgba(99, 102, 241, 0.25)" : "var(--line)"}
                    strokeWidth={val === 50 ? 1.5 : 1}
                    strokeDasharray={val === 50 ? "4 4" : undefined}
                  />
                  {/* Horizontal Grid Line */}
                  <line
                    x1={PAD_LEFT}
                    y1={yPos}
                    x2={PAD_LEFT + PLOT_WIDTH}
                    y2={yPos}
                    stroke={val === 50 ? "rgba(99, 102, 241, 0.25)" : "var(--line)"}
                    strokeWidth={val === 50 ? 1.5 : 1}
                    strokeDasharray={val === 50 ? "4 4" : undefined}
                  />
                  {/* X-axis numeric label */}
                  <text
                    x={xPos}
                    y={PAD_TOP + PLOT_HEIGHT + 20}
                    textAnchor="middle"
                    fill="var(--muted)"
                    fontSize="11"
                    fontWeight="600"
                  >
                    {val}
                  </text>
                  {/* Y-axis numeric label */}
                  <text
                    x={PAD_LEFT - 12}
                    y={yPos + 4}
                    textAnchor="end"
                    fill="var(--muted)"
                    fontSize="11"
                    fontWeight="600"
                  >
                    {val}
                  </text>
                </g>
              );
            })}

            {/* Diagonal Parity Line: Y = X (where Exposure == Risk) */}
            <line
              x1={getSvgX(0)}
              y1={getSvgY(0)}
              x2={getSvgX(100)}
              y2={getSvgY(100)}
              stroke="rgba(154, 150, 162, 0.35)"
              strokeWidth="1.5"
              strokeDasharray="5 5"
            />

            {/* Diagonal Parity Label */}
            <text
              x={getSvgX(88)}
              y={getSvgY(85) + 14}
              fill="#9a96a2"
              fontSize="10"
              fontWeight="700"
              textAnchor="start"
              transform={`rotate(-33, ${getSvgX(88)}, ${getSvgY(85)})`}
            >
              Parity (Risk = Exposure)
            </text>

            {/* Quadrant Subtitle Annotations */}
            <text
              x={getSvgX(75)}
              y={getSvgY(96)}
              fill="rgba(220, 38, 38, 0.6)"
              fontSize="11"
              fontWeight="800"
              textAnchor="middle"
              letterSpacing="0.04em"
            >
              HIGH EXPOSURE / HIGH RISK
            </text>
            <text
              x={getSvgX(75)}
              y={getSvgY(6)}
              fill="rgba(79, 70, 229, 0.7)"
              fontSize="11"
              fontWeight="800"
              textAnchor="middle"
              letterSpacing="0.04em"
            >
              HIGH EXPOSURE / HUMAN MOATS
            </text>
            <text
              x={getSvgX(25)}
              y={getSvgY(6)}
              fill="rgba(16, 185, 129, 0.7)"
              fontSize="11"
              fontWeight="800"
              textAnchor="middle"
              letterSpacing="0.04em"
            >
              LOW EXPOSURE / LOW RISK
            </text>

            {/* Axis Titles */}
            <text
              x={PAD_LEFT + PLOT_WIDTH / 2}
              y={SVG_HEIGHT - 12}
              textAnchor="middle"
              fill="var(--ink)"
              fontSize="13"
              fontWeight="800"
              letterSpacing="0.02em"
            >
              AI Exposure (0–100) →
            </text>
            <text
              x={18}
              y={PAD_TOP + PLOT_HEIGHT / 2}
              textAnchor="middle"
              fill="var(--ink)"
              fontSize="13"
              fontWeight="800"
              letterSpacing="0.02em"
              transform={`rotate(-90, 18, ${PAD_TOP + PLOT_HEIGHT / 2})`}
            >
              ↑ Replacement Risk (0–100)
            </text>

            {/* Plotted Dots */}
            {occupations.map((job) => {
              const cx = getSvgX(job.aiExposure);
              const cy = getSvgY(job.replacementRisk);
              const isFiltered = filteredOccupations.some((f) => f.slug === job.slug);
              const isSearchMatch = searchMatchedSlugs.size > 0 && searchMatchedSlugs.has(job.slug);
              const isSelected = selectedJob?.slug === job.slug;
              const isHovered = hoveredJob?.slug === job.slug;
              const isHighlighted = isSelected || isHovered || isSearchMatch;

              let opacity = 0.85;
              if (!isFiltered) opacity = 0.1;
              if (searchMatchedSlugs.size > 0 && !isSearchMatch) opacity = 0.15;
              if (isHighlighted) opacity = 1;

              const radius = isHighlighted ? 8.5 : 4.8;
              const color = getFieldColor(job.fieldSlug);

              return (
                <circle
                  key={job.slug}
                  cx={cx}
                  cy={cy}
                  r={radius}
                  fill={color}
                  opacity={opacity}
                  stroke={isHighlighted ? "white" : "rgba(255,255,255,0.8)"}
                  strokeWidth={isHighlighted ? 2.5 : 1}
                  filter={isHighlighted ? "url(#dot-shadow)" : undefined}
                  className="map-dot"
                  role="button"
                  tabIndex={0}
                  aria-label={`${job.title}: AI Exposure ${job.aiExposure}, Replacement Risk ${job.replacementRisk}`}
                  onClick={() => handleDotClick(job)}
                  onMouseEnter={(e) => handleDotHover(job, e)}
                  onMouseLeave={handleDotLeave}
                  onFocus={() => {
                    setHoveredJob(job);
                    setSelectedJob(job);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleDotClick(job);
                    }
                  }}
                />
              );
            })}

            {/* Active Selected Highlight Label in SVG for extra clarity */}
            {activeJob && (
              <g
                pointerEvents="none"
                transform={`translate(${getSvgX(activeJob.aiExposure)}, ${getSvgY(activeJob.replacementRisk) - 12})`}
              >
                <text
                  textAnchor="middle"
                  fill="var(--ink)"
                  fontSize="12"
                  fontWeight="850"
                  stroke="white"
                  strokeWidth="3"
                  paintOrder="stroke"
                >
                  {activeJob.title}
                </text>
              </g>
            )}
          </svg>

          {/* Desktop Hover Tooltip */}
          {hoveredJob && tooltipPos && (
            <div
              className="map-tooltip"
              style={{
                left: `${tooltipPos.x}px`,
                top: `${tooltipPos.y}px`,
              }}
            >
              <div className="tooltip-header">
                <strong>{hoveredJob.title}</strong>
                <span className="tooltip-field">{hoveredJob.fieldName}</span>
              </div>
              <div className="tooltip-scores">
                <div className="tooltip-score-item">
                  <span className="score-label">Exposure:</span>
                  <span className={getScoreSemantics("aiExposure", hoveredJob.aiExposure).badgeClass}>
                    {hoveredJob.aiExposure}
                  </span>
                </div>
                <div className="tooltip-score-item">
                  <span className="score-label">Risk:</span>
                  <span className={getScoreSemantics("replacementRisk", hoveredJob.replacementRisk).badgeClass}>
                    {hoveredJob.replacementRisk}
                  </span>
                </div>
              </div>
              <p className="tooltip-interpretation">
                {getDynamicInterpretation(hoveredJob.aiExposure, hoveredJob.replacementRisk)}
              </p>
              <div className="tooltip-hint">Click to view analysis →</div>
            </div>
          )}
        </div>
      </div>

      {/* Selected Occupation Card (Sticky / Responsive Inspector for Mobile & Click) */}
      {selectedJob && (
        <div className="map-selected-card card">
          <div className="selected-card-header">
            <div>
              <span className="section-kicker" style={{ color: getFieldColor(selectedJob.fieldSlug) }}>
                {selectedJob.fieldName}
              </span>
              <h3>{selectedJob.title}</h3>
            </div>
            <button
              type="button"
              className="selected-card-close"
              onClick={() => setSelectedJob(null)}
              aria-label="Close inspector"
            >
              ×
            </button>
          </div>

          <div className="selected-card-metrics">
            <div className="selected-metric">
              <span className="metric-title">AI Exposure</span>
              <span className={getScoreSemantics("aiExposure", selectedJob.aiExposure).badgeClass}>
                {selectedJob.aiExposure} / 100
              </span>
              <small className="muted">Task capability overlap</small>
            </div>
            <div className="selected-metric">
              <span className="metric-title">Replacement Risk</span>
              <span className={getScoreSemantics("replacementRisk", selectedJob.replacementRisk).badgeClass}>
                {selectedJob.replacementRisk} / 100
              </span>
              <small className="muted">Structural labour vulnerability</small>
            </div>
            <div className="selected-metric">
              <span className="metric-title">Capability Gap</span>
              <strong className="gap-value">
                {selectedJob.aiExposure - selectedJob.replacementRisk > 0 ? "+" : ""}
                {selectedJob.aiExposure - selectedJob.replacementRisk} pts
              </strong>
              <small className="muted">Human moat differential</small>
            </div>
          </div>

          <p className="selected-card-interpretation">
            {getDynamicInterpretation(selectedJob.aiExposure, selectedJob.replacementRisk)}
          </p>

          <div className="selected-card-action">
            <Link className="button primary" href={`/jobs/${selectedJob.slug}`}>
              View Full {selectedJob.title} Analysis →
            </Link>
          </div>
        </div>
      )}

      {/* Quadrant Legend & Educational Reference */}
      <div className="quadrant-guide-grid">
        <div className="card quadrant-card q-moat">
          <div className="quadrant-header">
            <span className="q-badge q-moat-badge">Shielded</span>
            <h4>High Exposure, Strong Human Moats</h4>
          </div>
          <p className="small">
            AI can assist with substantial analysis or drafting, but statutory accountability, high-stakes physical presence, or human trust limit direct workforce displacement.
          </p>
          <span className="muted small">e.g. Software Engineers, Nurse Practitioners, Financial Advisors</span>
        </div>

        <div className="card quadrant-card q-risk">
          <div className="quadrant-header">
            <span className="q-badge q-risk-badge">Elevated</span>
            <h4>High Exposure, Elevated Replacement Risk</h4>
          </div>
          <p className="small">
            High task overlap with algorithmic models, paired with standardized digital workflows and low physical or regulatory barriers to commercial automation.
          </p>
          <span className="muted small">e.g. Telemarketers, Data Entry Keyers, Title Examiners</span>
        </div>

        <div className="card quadrant-card q-safe">
          <div className="quadrant-header">
            <span className="q-badge q-safe-badge">Resilient</span>
            <h4>Low Exposure, Low Replacement Risk</h4>
          </div>
          <p className="small">
            Occupations centered around unpredictable physical environments, fine manual manipulation, emergency intervention, or specialized tactile tradecraft.
          </p>
          <span className="muted small">e.g. Electricians, Commercial Divers, Firefighters</span>
        </div>

        <div className="card quadrant-card q-mixed">
          <div className="quadrant-header">
            <span className="q-badge q-mixed-badge">Moderate</span>
            <h4>Moderate / Mixed Constraints</h4>
          </div>
          <p className="small">
            Hybrid occupations balancing specialized localized judgment, physical logistics, and moderate digital coordination.
          </p>
          <span className="muted small">e.g. Construction Managers, Logistics Planners</span>
        </div>
      </div>
    </div>
  );
}
