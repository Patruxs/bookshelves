import { forwardRef, type AnchorHTMLAttributes } from "react";
import { Link } from "react-router-dom";

interface RouterLinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  href?: string;
  to?: string;
}

function isExternal(href: string): boolean {
  return /^(https?:)?\/\//i.test(href) || href.startsWith("mailto:") || href.startsWith("#");
}

export const RouterLink = forwardRef<HTMLAnchorElement, RouterLinkProps>(function RouterLink({ href, to, children, ...rest }, ref) {
  const destination = to ?? href ?? "";
  if (!destination || isExternal(destination) || rest.target === "_blank" || rest.download !== undefined) {
    return (
      <a ref={ref} href={destination} {...rest}>
        {children}
      </a>
    );
  }
  return (
    <Link ref={ref} to={destination} {...rest}>
      {children}
    </Link>
  );
});
