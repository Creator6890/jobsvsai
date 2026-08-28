"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, useId } from "react";

export interface NavDropdownItem {
  href: string;
  title: string;
  description: string;
}

interface NavDropdownProps {
  label: string;
  items: NavDropdownItem[];
}

export function NavDropdown({ label, items }: NavDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname() ?? "";
  const [prevPathname, setPrevPathname] = useState(pathname);
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const itemRefs = useRef<(HTMLAnchorElement | null)[]>([]);
  const menuId = useId();

  if (prevPathname !== pathname) {
    setPrevPathname(pathname);
    setIsOpen(false);
  }

  const isAnyActive = items.some(
    (item) => pathname === item.href || (item.href !== "/" && pathname.startsWith(`${item.href}/`))
  );

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

  function handleBlur(event: React.FocusEvent) {
    const nextTarget = event.relatedTarget as Node | null;
    if (dropdownRef.current && nextTarget && !dropdownRef.current.contains(nextTarget)) {
      setIsOpen(false);
    }
  }

  function handleButtonKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setIsOpen(true);
      setTimeout(() => itemRefs.current[0]?.focus(), 30);
    } else if (event.key === "Escape" && isOpen) {
      event.preventDefault();
      setIsOpen(false);
    }
  }

  function handleItemKeyDown(index: number, event: React.KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      setIsOpen(false);
      buttonRef.current?.focus();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      const nextIndex = (index + 1) % items.length;
      itemRefs.current[nextIndex]?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (index === 0) {
        buttonRef.current?.focus();
      } else {
        itemRefs.current[index - 1]?.focus();
      }
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
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-controls={menuId}
        onClick={() => setIsOpen((prev) => !prev)}
        onKeyDown={handleButtonKeyDown}
      >
        <span>{label}</span>
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
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      <div
        id={menuId}
        className="nav-dropdown-menu"
        role="menu"
        aria-label={`${label} submenu`}
        hidden={!isOpen}
      >
        {items.map((item, idx) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(`${item.href}/`));
          return (
            <Link
              key={item.href}
              ref={(el) => { itemRefs.current[idx] = el; }}
              href={item.href}
              role="menuitem"
              className={`nav-dropdown-item ${isActive ? "current" : ""}`}
              onClick={() => setIsOpen(false)}
              onKeyDown={(e) => handleItemKeyDown(idx, e)}
            >
              <div className="dropdown-item-header">
                <span className="dropdown-item-title">{item.title}</span>
                <span className="dropdown-item-arrow" aria-hidden="true">→</span>
              </div>
              <span className="dropdown-item-desc">{item.description}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
