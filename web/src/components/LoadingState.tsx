import { Button } from "@astryxdesign/core/Button";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { Grid } from "@astryxdesign/core/Grid";
import { Skeleton } from "@astryxdesign/core/Skeleton";
import { VStack } from "@astryxdesign/core/VStack";
import { useLibrary } from "../lib/library";

export function CoverSkeletonGrid({ count = 12 }: { count?: number }) {
  return (
    <Grid columns={{ minWidth: 150 }} gap={4} className="book-grid">
      {Array.from({ length: count }, (_, index) => (
        <VStack key={index} gap={2}>
          <div className="book-cover">
            <Skeleton index={index} radius={2} />
          </div>
          <Skeleton height={16} width="85%" index={index} />
          <Skeleton height={12} width="55%" index={index} />
        </VStack>
      ))}
    </Grid>
  );
}

export function LoadErrorState() {
  const { error, reload } = useLibrary();
  return (
    <EmptyState
      title="The library could not be loaded"
      description={error || "data.json could not be fetched."}
      actions={<Button label="Try again" variant="primary" onClick={reload} />}
    />
  );
}
