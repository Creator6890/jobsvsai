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
  const item0Ref = useRef<HTMLAnchorElement | null>(null);
  const item1Ref = useRef<HTMLAnchorElement | null>(null);
  const menuId = useId();

  // Reset open state when navigating to a new pathname without calling setState in an effect
  if (prevPathname !== pathname) {
    setPrevPathname(pathname);
    setIsOpen(false);
  }

  const isCareerFitActive = pathname === "/career-fit" || pathname.startsWith("/career-fit/");
  const isCompareActive = pathname === "/compare" || pathname.startsWith("/compare/");
  const isAnyActive = isCareerFitActive || isCompareActive;

  // Close when clicking or touching outside
  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("pointerdown", handlePointerDown);
    }
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [isOpen]);

  // Close on focusout when focus leaves the entire dropdown container
  function handleBlur(event: React.FocusEvent) {
    const nextTarget = event.relatedTarget as Node | null;
    if (dropdownRef.current && nextTarget && !dropdownRef.current.contains(nextTarget)) {
      setIsOpen(false);
    }
  }

  // Keyboard navigation on the trigger button
  function handleButtonKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setIsOpen(true);
      setTimeout(() => item0Ref.current?.focus(), 20);
    } else if (event.key === "Escape" && isOpen) {
      event.preventDefault();
      setIsOpen(false);
    }
  }

  // Keyboard navigation on item 0 (Career Fit)
  function handleItem0KeyDown(event: React.KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      setIsOpen(false);
      buttonRef.current?.focus();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      item1Ref.current?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      buttonRef.current?.focus();
    }
  }

  // Keyboard navigation on item 1 (Compare Careers)
  function handleItem1KeyDown(event: React.KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      setIsOpen(false);
      buttonRef.current?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      item0Ref.current?.focus();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      item0Ref.current?.focus();
    }
  }

  return (
    <div
      className={`nav-dropdown ${isOpen ? "open" : ""}`}
      ref={dropdownRef}
      onBlur={handleBlur}
    >
      <button
        ref={buttonRef}
        type="button"
        className={`nav-dropdown-toggle ${isAnyActive ? "active" : ""}`}
        aria-expanded={isOpen}
        aria-haspopup="true"
        aria-controls={menuId}
        onClick={() => setIsOpen((prev) => !prev)}
        onKeyDown={handleButtonKeyDown}
      >
        <span>Career Tools</span>
        <svg
          className="dropdown-chevron"
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M2.5 4.5L6 8L9.5 4.5"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      <div
        className="nav-dropdown-menu"
        id={menuId}
        role="menu"
        aria-hidden={!isOpen}
      >
        <Link
          ref={item0Ref}
          href="/career-fit"
          className={`nav-dropdown-item ${isCareerFitActive ? "current" : ""}`}
          role="menuitem"
          tabIndex={isOpen ? 0 : -1}
          onKeyDown={handleItem0KeyDown}
        >
          <div className="dropdown-item-header">
            <strong className="dropdown-item-title">Career Fit</strong>
            <span className="dropdown-item-arrow" aria-hidden="true">→</span>
          </div>
          <span className="dropdown-item-desc">
            Find careers aligned with your work preferences and strengths.
          </span>
        </Link>

        <div className="dropdown-divider" role="separator" aria-hidden="true" />

        <Link
          ref={item1Ref}
          href="/compare"
          className={`nav-dropdown-item ${isCompareActive ? "current" : ""}`}
          role="menuitem"
          tabIndex={isOpen ? 0 : -1}
          onKeyDown={handleItem1KeyDown}
        >
          <div className="dropdown-item-header">
            <strong className="dropdown-item-title">Compare Careers</strong>
            <span className="dropdown-item-arrow" aria-hidden="true">→</span>
          </div>
          <span className="dropdown-item-desc">
            Compare AI Exposure and Replacement Risk side by side.
          </span>
        </Link>
      </div>
    </div>
  );
}
