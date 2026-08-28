import Link from "next/link";

export type BreadcrumbItem = {
  name: string;
  item: string;
};

export function Breadcrumbs({ items }: { items: BreadcrumbItem[] }) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((crumb, idx) => ({
      "@type": "ListItem",
      position: idx + 1,
      name: crumb.name,
      item: crumb.item.startsWith("http") ? crumb.item : `https://jobsvsai.com${crumb.item}`,
    })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        {items.map((crumb, idx) => {
          const isLast = idx === items.length - 1;
          return (
            <span key={crumb.item} style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
              {isLast ? (
                <span className="breadcrumbs-current" aria-current="page">
                  {crumb.name}
                </span>
              ) : (
                <>
                  <Link href={crumb.item}>{crumb.name}</Link>
                  <span className="breadcrumbs-sep" aria-hidden="true">/</span>
                </>
              )}
            </span>
          );
        })}
      </nav>
    </>
  );
}
