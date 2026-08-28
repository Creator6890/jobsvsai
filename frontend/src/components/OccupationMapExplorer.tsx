"use client";

import { useId, useMemo, useState, useRef, useEffect, useCallback } from "react";
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

interface SearchSuggestionItem {
  slug: string;
  title: string;
  category: string;
  isPreliminary: boolean;
  aiExposure: number;
  replacementRisk: number;
  confidenceLabel?: string;
}

interface ApiVerifiedResult {
  slug: string;
  title: string;
  category: string;
  aiExposure: number;
  replacementRisk: number;
}

interface ApiEstimatedResult {
  slug: string;
  title: string;
  category: string;
  aiExposure: number;
  replacementRisk: number;
  confidenceLabel?: string;
}

const FIELD_COLORS: Record<string, string> = {
  "business-finance": "#3b82f6",
  "technology-data": "#6366f1",
  "office-administration": "#64748b",
  "healthcare": "#0891b2",
  "science-research": "#7c3aed",
  "engineering": "#0284c7",
  "education": "#059669",
  "community-social-services": "#0d9488",
  "legal": "#d97706",
  "management": "#4f46e5",
  "sales": "#ea580c",
  "creative-media": "#db2777",
  "protective-services": "#dc2626",
  "food-hospitality": "#e11d48",
  "personal-care-services": "#9333ea",
  "agriculture-environment": "#65a30d",
  "skilled-trades": "#78716c",
  "transportation": "#2563eb",
  "production": "#475569",
};

function getFieldColor(fieldSlug: string): string {
  return FIELD_COLORS[fieldSlug] || "#6366f1";
}

function getDynamicInterpretation(aiExposure: number, replacementRisk: number): string {
  if (aiExposure >= 60 && replacementRisk < 50) {
    return "High capability overlap with AI, but physical constraints, accountability, or regulatory factors significantly buffer structural replacement pressure.";
  }
  if (aiExposure >= 60 && replacementRisk >= 60) {
    return "High capability exposure coupled with elevated structural replacement vulnerability across standardized digital workflows.";
  }
  if (aiExposure < 40 && replacementRisk < 40) {
    return "Lower AI capability overlap; physical execution, unpredictable environments, or manual tradecraft remain primary.";
  }
  if (aiExposure < 50 && replacementRisk >= 50) {
    return "Lower overall AI capability overlap, but specialized structural pressure or commercial consolidation in specific task areas.";
  }
  return "Moderate task capability overlap balanced with structural oversight and human responsibility.";
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
  const [isSearching, setIsSearching] = useState(false);
  const [apiSuggestions, setApiSuggestions] = useState<SearchSuggestionItem[]>([]);
  const [selectedField, setSelectedField] = useState<string>("all");
  const [selectedRiskBand, setSelectedRiskBand] = useState<string>("all");
  const [selectedExposureBand, setSelectedExposureBand] = useState<string>("all");

  const [hoveredJob, setHoveredJob] = useState<ExplorerOccupation | null>(null);
  const [selectedJob, setSelectedJob] = useState<ExplorerOccupation | null>(null);
  const [selectedPreliminaryJob, setSelectedPreliminaryJob] = useState<SearchSuggestionItem | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);
  const [isSearchFocused, setIsSearchFocused] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  // SVG Geometry Constants (Clean 4:3 near-square aspect ratio)
  const SVG_WIDTH = 760;
  const SVG_HEIGHT = 560;
  const PAD_LEFT = 55;
  const PAD_RIGHT = 30;
  const PAD_TOP = 30;
  const PAD_BOTTOM = 55;

  const PLOT_WIDTH = SVG_WIDTH - PAD_LEFT - PAD_RIGHT; // 675
  const PLOT_HEIGHT = SVG_HEIGHT - PAD_TOP - PAD_BOTTOM; // 475

  const getSvgX = useCallback(
    (exposure: number) => PAD_LEFT + (Math.max(0, Math.min(100, exposure)) / 100) * PLOT_WIDTH,
    [PAD_LEFT, PLOT_WIDTH]
  );
  const getSvgY = useCallback(
    (risk: number) => PAD_TOP + PLOT_HEIGHT - (Math.max(0, Math.min(100, risk)) / 100) * PLOT_HEIGHT,
    [PAD_TOP, PLOT_HEIGHT]
  );

  // Search V2 Query with Debounce
  useEffect(() => {
    const q = searchQuery.trim();
    if (q.length < 2) {
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await fetch(`/api/occupations/search/resolve?q=${encodeURIComponent(q)}`);
        if (!res.ok) throw new Error("Search failed");
        const data = await res.json();

        const suggestions: SearchSuggestionItem[] = [];
        const resultOrder: string[] = data.resultOrder || [];
        const verifiedMap = new Map<string, ApiVerifiedResult>(
          (data.results || []).map((r: ApiVerifiedResult) => [r.slug, r])
        );
        const estimatedMap = new Map<string, ApiEstimatedResult>(
          (data.estimatedResults || []).map((r: ApiEstimatedResult) => [r.slug, r])
        );

        for (const slug of resultOrder) {
          const verified = verifiedMap.get(slug);
          const estimated = estimatedMap.get(slug);

          if (verified) {
            suggestions.push({
              slug: verified.slug,
              title: verified.title,
              category: verified.category,
              isPreliminary: false,
              aiExposure: Math.round(Number(verified.aiExposure)),
              replacementRisk: Math.round(Number(verified.replacementRisk)),
            });
          } else if (estimated) {
            suggestions.push({
              slug: estimated.slug,
              title: estimated.title,
              category: estimated.category,
              isPreliminary: true,
              aiExposure: Math.round(Number(estimated.aiExposure)),
              replacementRisk: Math.round(Number(estimated.replacementRisk)),
              confidenceLabel: estimated.confidenceLabel,
            });
          }
          if (suggestions.length >= 7) break;
        }

        setApiSuggestions(suggestions);
      } catch (err) {
        console.error("Search error:", err);
      } finally {
        setIsSearching(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [searchQuery]);

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
    setSelectedPreliminaryJob(null);
    setHoveredJob(null);
    setApiSuggestions([]);
  };

  const handleDotClick = (job: ExplorerOccupation) => {
    setSelectedPreliminaryJob(null);
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

  // Robust Nearest-Point Touch / Click on SVG Canvas
  const handleSvgCanvasClick = (e: React.MouseEvent<SVGSVGElement> | React.TouchEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const svgRect = svgRef.current.getBoundingClientRect();
    const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
    const clientY = "touches" in e ? e.touches[0].clientY : e.clientY;

    const xRatio = (clientX - svgRect.left) / svgRect.width;
    const yRatio = (clientY - svgRect.top) / svgRect.height;

    const svgClickX = xRatio * SVG_WIDTH;
    const svgClickY = yRatio * SVG_HEIGHT;

    // Find nearest point within 26px radius in SVG space
    let minDistance = 26;
    let closestJob: ExplorerOccupation | null = null;

    for (const job of filteredOccupations) {
      const dotX = getSvgX(job.aiExposure);
      const dotY = getSvgY(job.replacementRisk);
      const dist = Math.sqrt(Math.pow(svgClickX - dotX, 2) + Math.pow(svgClickY - dotY, 2));
      if (dist < minDistance) {
        minDistance = dist;
        closestJob = job;
      }
    }

    if (closestJob) {
      setSelectedPreliminaryJob(null);
      setSelectedJob(closestJob);
      setHoveredJob(closestJob);
    }
  };

  // Select item from Search V2 suggestions
  const handleSelectSuggestion = (item: SearchSuggestionItem) => {
    setSearchQuery(item.title);
    setIsSearchFocused(false);

    if (item.isPreliminary) {
      setSelectedJob(null);
      setSelectedPreliminaryJob(item);
    } else {
      setSelectedPreliminaryJob(null);
      const matched = occupations.find((o) => o.slug === item.slug);
      if (matched) {
        setSelectedJob(matched);
        setHoveredJob(matched);
      }
    }
  };

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
              placeholder="Search verified occupation (e.g. Accountant, Teacher)..."
              value={searchQuery}
              onChange={(e) => {
                const val = e.target.value;
                setSearchQuery(val);
                if (val.trim().length < 2) {
                  setApiSuggestions([]);
                  setIsSearching(false);
                }
              }}
              onFocus={() => setIsSearchFocused(true)}
              onBlur={() => setTimeout(() => setIsSearchFocused(false), 280)}
              autoComplete="off"
            />
            {searchQuery && (
              <button
                type="button"
                className="map-search-clear"
                onClick={() => {
                  setSearchQuery("");
                  setApiSuggestions([]);
                  setSelectedJob(null);
                  setSelectedPreliminaryJob(null);
                }}
                aria-label="Clear search"
              >
                ×
              </button>
            )}

            {/* Search V2 Dropdown Suggestions */}
            {(isSearchFocused || searchQuery.trim().length >= 2) && (
              <ul className="map-search-dropdown" role="listbox">
                {isSearching && apiSuggestions.length === 0 && (
                  <li className="map-search-status muted small" style={{ padding: "10px 14px" }}>
                    Searching occupations...
                  </li>
                )}
                {!isSearching && apiSuggestions.length === 0 && searchQuery.trim().length >= 2 && (
                  <li className="map-search-status muted small" style={{ padding: "10px 14px" }}>
                    No matching occupations found.
                  </li>
                )}
                {apiSuggestions.map((item) => (
                  <li
                    key={item.slug}
                    role="option"
                    aria-selected={selectedJob?.slug === item.slug || selectedPreliminaryJob?.slug === item.slug}
                    className="map-search-option"
                    onMouseDown={() => handleSelectSuggestion(item)}
                    onClick={() => handleSelectSuggestion(item)}
                  >
                    <div className="option-main">
                      <span className="option-title">{item.title}</span>
                      {item.isPreliminary ? (
                        <span className="badge-preliminary-tag">Preliminary</span>
                      ) : (
                        <span className="badge-verified-tag">Verified</span>
                      )}
                    </div>
                    <span className="option-meta">
                      Exp: {item.aiExposure} | Risk: {item.replacementRisk}
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
          <span className="muted small"> (Filtered cohort active)</span>
        )}
      </div>

      {/* Interactive 2D Scatter Chart */}
      <div className="map-chart-card card">
        <div className="map-svg-container">
          <svg
            ref={svgRef}
            viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
            className="map-svg"
            role="img"
            aria-label="2D Scatter plot comparing AI Exposure on the X-axis and Replacement Risk on the Y-axis across occupations"
            onClick={handleSvgCanvasClick}
          >
            <defs>
              <filter id="dot-shadow" x="-50%" y="-50%" width="200%" height="200%">
                <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.28" />
              </filter>
            </defs>

            {/* Quadrant Background Tints */}
            {/* Top-Right: High Exposure / Elevated Risk */}
            <rect
              x={getSvgX(50)}
              y={getSvgY(100)}
              width={PLOT_WIDTH / 2}
              height={PLOT_HEIGHT / 2}
              fill="rgba(239, 68, 68, 0.032)"
              className="quadrant-rect"
            />
            {/* Bottom-Right: High Exposure / Lower Replacement Pressure */}
            <rect
              x={getSvgX(50)}
              y={getSvgY(50)}
              width={PLOT_WIDTH / 2}
              height={PLOT_HEIGHT / 2}
              fill="rgba(99, 102, 241, 0.038)"
              className="quadrant-rect"
            />
            {/* Bottom-Left: Low Exposure / Low Risk */}
            <rect
              x={getSvgX(0)}
              y={getSvgY(50)}
              width={PLOT_WIDTH / 2}
              height={PLOT_HEIGHT / 2}
              fill="rgba(16, 185, 129, 0.032)"
              className="quadrant-rect"
            />
            {/* Top-Left: Lower Exposure / Higher Structural Pressure */}
            <rect
              x={getSvgX(0)}
              y={getSvgY(100)}
              width={PLOT_WIDTH / 2}
              height={PLOT_HEIGHT / 2}
              fill="rgba(245, 158, 11, 0.028)"
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
                    stroke={val === 50 ? "rgba(99, 102, 241, 0.22)" : "var(--line)"}
                    strokeWidth={val === 50 ? 1.5 : 1}
                    strokeDasharray={val === 50 ? "4 4" : undefined}
                  />
                  {/* Horizontal Grid Line */}
                  <line
                    x1={PAD_LEFT}
                    y1={yPos}
                    x2={PAD_LEFT + PLOT_WIDTH}
                    y2={yPos}
                    stroke={val === 50 ? "rgba(99, 102, 241, 0.22)" : "var(--line)"}
                    strokeWidth={val === 50 ? 1.5 : 1}
                    strokeDasharray={val === 50 ? "4 4" : undefined}
                  />
                  {/* X-axis numeric tick label */}
                  <text
                    x={xPos}
                    y={PAD_TOP + PLOT_HEIGHT + 18}
                    textAnchor="middle"
                    fill="var(--muted)"
                    fontSize="11"
                    fontWeight="650"
                  >
                    {val}
                  </text>
                  {/* Y-axis numeric tick label */}
                  <text
                    x={PAD_LEFT - 10}
                    y={yPos + 4}
                    textAnchor="end"
                    fill="var(--muted)"
                    fontSize="11"
                    fontWeight="650"
                  >
                    {val}
                  </text>
                </g>
              );
            })}

            {/* Exposure–Replacement Parity Line (Y = X) */}
            <line
              x1={getSvgX(0)}
              y1={getSvgY(0)}
              x2={getSvgX(100)}
              y2={getSvgY(100)}
              stroke="rgba(148, 163, 184, 0.45)"
              strokeWidth="1.5"
              strokeDasharray="5 5"
            />

            {/* Parity Line Label */}
            <text
              x={getSvgX(84)}
              y={getSvgY(82) + 14}
              fill="#94a3b8"
              fontSize="10"
              fontWeight="700"
              textAnchor="start"
              transform={`rotate(-35, ${getSvgX(84)}, ${getSvgY(82)})`}
            >
              Parity (Exposure = Risk)
            </text>

            {/* Quadrant Zone Labels */}
            <text
              x={getSvgX(75)}
              y={getSvgY(97)}
              fill="rgba(220, 38, 38, 0.65)"
              fontSize="10.5"
              fontWeight="800"
              textAnchor="middle"
              letterSpacing="0.04em"
            >
              HIGH EXPOSURE / ELEVATED RISK
            </text>
            <text
              x={getSvgX(75)}
              y={getSvgY(5)}
              fill="rgba(79, 70, 229, 0.75)"
              fontSize="10.5"
              fontWeight="800"
              textAnchor="middle"
              letterSpacing="0.04em"
            >
              HIGH EXPOSURE / LOWER RISK
            </text>
            <text
              x={getSvgX(25)}
              y={getSvgY(97)}
              fill="rgba(217, 119, 6, 0.65)"
              fontSize="10.5"
              fontWeight="800"
              textAnchor="middle"
              letterSpacing="0.04em"
            >
              LOWER EXPOSURE / HIGHER RISK
            </text>
            <text
              x={getSvgX(25)}
              y={getSvgY(5)}
              fill="rgba(16, 185, 129, 0.75)"
              fontSize="10.5"
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
              fontSize="12.5"
              fontWeight="800"
              letterSpacing="0.02em"
            >
              AI Exposure (0–100) →
            </text>
            <text
              x={16}
              y={PAD_TOP + PLOT_HEIGHT / 2}
              textAnchor="middle"
              fill="var(--ink)"
              fontSize="12.5"
              fontWeight="800"
              letterSpacing="0.02em"
              transform={`rotate(-90, 16, ${PAD_TOP + PLOT_HEIGHT / 2})`}
            >
              ↑ Replacement Risk (0–100)
            </text>

            {/* Plotted Dots (507 Verified Points) */}
            {occupations.map((job) => {
              const cx = getSvgX(job.aiExposure);
              const cy = getSvgY(job.replacementRisk);
              const isFiltered = filteredOccupations.some((f) => f.slug === job.slug);
              const isSelected = selectedJob?.slug === job.slug;
              const isHovered = hoveredJob?.slug === job.slug;

              let opacity = 0.72;
              if (!isFiltered) opacity = 0.08;
              if (selectedJob && !isSelected) opacity = 0.22;
              if (isSelected || isHovered) opacity = 1;

              const radius = 3.8;
              const color = getFieldColor(job.fieldSlug);

              return (
                <g key={job.slug} className="dot-group">
                  {/* Larger Invisible Hit Target (Radius 14px) for robust touch interaction */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={14}
                    fill="transparent"
                    className="touch-hit-target"
                    onClick={() => handleDotClick(job)}
                    onMouseEnter={(e) => handleDotHover(job, e)}
                    onMouseLeave={handleDotLeave}
                  />

                  {/* Visible Plotted Dot */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={radius}
                    fill={color}
                    opacity={opacity}
                    stroke="rgba(255, 255, 255, 0.85)"
                    strokeWidth={0.8}
                    className="map-dot"
                    pointerEvents="none"
                  />
                </g>
              );
            })}

            {/* Active Selected Marker Layer (Always on top) */}
            {selectedJob && (
              <g className="active-selected-marker" pointerEvents="none">
                {/* Outer pulsing ring */}
                <circle
                  cx={getSvgX(selectedJob.aiExposure)}
                  cy={getSvgY(selectedJob.replacementRisk)}
                  r={16}
                  fill="none"
                  stroke="var(--violet)"
                  strokeWidth={2}
                  strokeDasharray="4 3"
                  opacity={0.8}
                />
                {/* Inner white border */}
                <circle
                  cx={getSvgX(selectedJob.aiExposure)}
                  cy={getSvgY(selectedJob.replacementRisk)}
                  r={9.5}
                  fill="white"
                  filter="url(#dot-shadow)"
                />
                {/* Core colored point */}
                <circle
                  cx={getSvgX(selectedJob.aiExposure)}
                  cy={getSvgY(selectedJob.replacementRisk)}
                  r={7.5}
                  fill={getFieldColor(selectedJob.fieldSlug)}
                />
                {/* Callout Title Label */}
                <text
                  x={getSvgX(selectedJob.aiExposure)}
                  y={getSvgY(selectedJob.replacementRisk) - 14}
                  textAnchor="middle"
                  fill="var(--ink)"
                  fontSize="12"
                  fontWeight="850"
                  stroke="white"
                  strokeWidth="3"
                  paintOrder="stroke"
                >
                  {selectedJob.title}
                </text>
              </g>
            )}
          </svg>

          {/* Desktop Hover Tooltip */}
          {hoveredJob && tooltipPos && !selectedJob && (
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

      {/* Selected Verified Occupation Card */}
      {selectedJob && (
        <div className="map-selected-card card">
          <div className="selected-card-header">
            <div>
              <span className="section-kicker" style={{ color: getFieldColor(selectedJob.fieldSlug) }}>
                {selectedJob.fieldName} · Verified Analysis
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
              <span className="metric-title">Score Gap</span>
              <strong className="gap-value">
                {selectedJob.aiExposure - selectedJob.replacementRisk > 0 ? "+" : ""}
                {selectedJob.aiExposure - selectedJob.replacementRisk} pts
              </strong>
              <small className="muted">Exposure − Risk differential</small>
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

      {/* Preliminary Search Result Banner / Card */}
      {selectedPreliminaryJob && (
        <div className="map-selected-card card preliminary-info-card">
          <div className="selected-card-header">
            <div>
              <span className="section-kicker" style={{ color: "var(--amber)" }}>
                {selectedPreliminaryJob.category} · Preliminary Estimate
              </span>
              <h3>{selectedPreliminaryJob.title}</h3>
            </div>
            <button
              type="button"
              className="selected-card-close"
              onClick={() => setSelectedPreliminaryJob(null)}
              aria-label="Close message"
            >
              ×
            </button>
          </div>

          <div className="preliminary-notice-box">
            <p>
              <strong>{selectedPreliminaryJob.title}</strong> currently has a Preliminary estimate and is not included in this Verified occupation map.
            </p>
          </div>

          <div className="selected-card-metrics">
            <div className="selected-metric">
              <span className="metric-title">Estimated Exposure</span>
              <span className={getScoreSemantics("aiExposure", selectedPreliminaryJob.aiExposure, { isEstimated: true }).badgeClass}>
                ~{selectedPreliminaryJob.aiExposure} / 100
              </span>
              <small className="muted">Preliminary model estimate</small>
            </div>
            <div className="selected-metric">
              <span className="metric-title">Estimated Risk</span>
              <span className={getScoreSemantics("replacementRisk", selectedPreliminaryJob.replacementRisk, { isEstimated: true }).badgeClass}>
                ~{selectedPreliminaryJob.replacementRisk} / 100
              </span>
              <small className="muted">Preliminary model estimate</small>
            </div>
            <div className="selected-metric">
              <span className="metric-title">Evidence Status</span>
              <span className="badge-preliminary-tag">
                {selectedPreliminaryJob.confidenceLabel || "Preliminary"}
              </span>
              <small className="muted">Task breakdown pending</small>
            </div>
          </div>

          <div className="selected-card-action">
            <Link className="button primary" href={`/jobs/${selectedPreliminaryJob.slug}`}>
              View {selectedPreliminaryJob.title} Analysis →
            </Link>
          </div>
        </div>
      )}

      {/* Quadrant Guide & Educational Reference */}
      <div className="quadrant-guide-grid">
        <div className="card quadrant-card q-moat">
          <div className="quadrant-header">
            <span className="q-badge q-moat-badge">Buffered</span>
            <h4>High Exposure / Lower Replacement Pressure</h4>
          </div>
          <p className="small">
            AI can assist with substantial analysis or drafting, but human dependency, physical requirements, accountability, regulation, adoption, or labour-market friction buffer structural displacement.
          </p>
          <span className="muted small">e.g. Software Engineers, Nurse Practitioners, Financial Advisors</span>
        </div>

        <div className="card quadrant-card q-risk">
          <div className="quadrant-header">
            <span className="q-badge q-risk-badge">Elevated</span>
            <h4>High Exposure / Elevated Replacement Risk</h4>
          </div>
          <p className="small">
            High task overlap with algorithmic models, paired with standardized digital workflows and lower physical or regulatory barriers to commercial automation.
          </p>
          <span className="muted small">e.g. Telemarketers, Data Entry Keyers, Title Examiners</span>
        </div>

        <div className="card quadrant-card q-safe">
          <div className="quadrant-header">
            <span className="q-badge q-safe-badge">Resilient</span>
            <h4>Low Exposure / Low Replacement Risk</h4>
          </div>
          <p className="small">
            Occupations centered around unpredictable physical environments, fine manual manipulation, emergency intervention, or specialized tactile tradecraft.
          </p>
          <span className="muted small">e.g. Electricians, Commercial Divers, Firefighters</span>
        </div>

        <div className="card quadrant-card q-mixed">
          <div className="quadrant-header">
            <span className="q-badge q-mixed-badge">Structural</span>
            <h4>Lower Exposure / Higher Structural Pressure</h4>
          </div>
          <p className="small">
            Lower overall AI capability overlap, but specialized structural or commercial vulnerability in specific routine or consolidating tasks.
          </p>
          <span className="muted small">e.g. Specialized Clerks, Dispatchers</span>
        </div>
      </div>
    </div>
  );
}
