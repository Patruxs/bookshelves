import { Button } from "@astryxdesign/core/Button";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { PageFrame } from "../components/PageFrame";
import { useDocumentTitle } from "../lib/hooks";

export function NotFoundPage() {
  useDocumentTitle("Page not found");
  return (
    <PageFrame>
      <EmptyState
        title="Page not found"
        description="The address does not match anything in the library."
        actions={<Button label="Go home" variant="primary" href="/home" />}
      />
    </PageFrame>
  );
}
