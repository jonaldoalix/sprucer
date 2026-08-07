"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/applications", label: "Applications" },
  { href: "/knowledge", label: "Knowledge" },
  { href: "/login", label: "Login" },
];

export function SiteNav() {
  const pathname = usePathname();
  return (
    <nav className="nav">
      {links.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          data-active={pathname === link.href || pathname.startsWith(link.href + "/")}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
