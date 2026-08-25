"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, useId } from "react";

export function CareerToolsDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname() ?? "";
  const [prevPathname, setPrevPathname] = useState(pathname);
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const menuId = useId();

  // Reset open state when navigating to a new pathname without calling setState in an effect
  if (prevPathname !== pathname) {
    setPrevPathname(pathname);
    setIsOpen(false);
  }

  const isCareerFitActive = pathname === "/career-fit" || pathname.startsWith("/career-fit/");
  const isCompareActive = pathname === "/compare" || pathname.startsWith("/compare/");
  const isAnyActive = isCareerFitActive || isCompareActive;

  // Close when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  // Close when pressing Escape
  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === "Escape") {
      setIsOpen(false);
      buttonRef.current?.focus();
    } else if (event.key === "ArrowDown" && !isOpen) {
      event.preventDefault();
      setIsOpen(true);
    }
  }

  return (
    <div
      className={`nav-dropdown ${isOpen ? "open" : ""}`}
      ref={dropdownRef}
      onKeyDown={handleKeyDown}
    >
      <button
        ref={buttonRef}
        type="button"
        className={`nav-dropdown-toggle ${isAnyActive ? "active" : ""}`}
        aria-expanded={isOpen}
        aria-haspopup="true"
        aria-controls={menuId}
        onClick={() => setIsOpen((prev) => !prev)}
      >
        <span>Career Tools</span>
        <span className="dropdown-chevron" aria-hidden="true">
          ▾
        </span>
      </button>

      {isOpen && (
        <div className="nav-dropdown-menu" id={menuId} role="menu">
          <Link
            href="/career-fit"
            className={`nav-dropdown-item ${isCareerFitActive ? "current" : ""}`}
            role="menuitem"
            onClick={() => setIsOpen(false)}
          >
            <strong className="dropdown-item-title">Career Fit</strong>
            <span className="dropdown-item-desc">
              Find careers aligned with your work preferences and strengths.
            </span>
          </Link>

          <Link
            href="/compare"
            className={`nav-dropdown-item ${isCompareActive ? "current" : ""}`}
            role="menuitem"
            onClick={() => setIsOpen(false)}
          >
            <strong className="dropdown-item-title">Compare Careers</strong>
            <span className="dropdown-item-desc">
              Compare AI Exposure and Replacement Risk side by side.
            </span>
          </Link>
        </div>
      )}
    </div>
  );
}
