"use client";

import { ThumbsUp, ThumbsDown } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import {
  useFeedbackCheck,
  useFeedbackStats,
  useSubmitKBFeedback,
} from "@/hooks/useKB";

interface FeedbackWidgetProps {
  articleId: string;
}

export function FeedbackWidget({ articleId }: FeedbackWidgetProps) {
  const { data: check } = useFeedbackCheck(articleId);
  const { data: stats } = useFeedbackStats(articleId);
  const submit = useSubmitKBFeedback(articleId);

  const currentVote = check?.has_feedback ? check.is_helpful : null;

  return (
    <div className="flex flex-col gap-2 pt-2 border-t border-border">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm text-muted-foreground">
          ¿Te fue útil este artículo?
        </span>
        <Button
          size="sm"
          variant={currentVote === true ? "default" : "outline"}
          onClick={() => submit.mutate({ is_helpful: true })}
          loading={submit.isPending}
        >
          <ThumbsUp className="h-3.5 w-3.5 mr-1" />
          Sí
        </Button>
        <Button
          size="sm"
          variant={currentVote === false ? "default" : "outline"}
          onClick={() => submit.mutate({ is_helpful: false })}
          loading={submit.isPending}
        >
          <ThumbsDown className="h-3.5 w-3.5 mr-1" />
          No
        </Button>
      </div>
      {stats && stats.total > 0 && (
        <p className="text-xs text-muted-foreground">
          {stats.helpful_count} de {stats.total} usuario
          {stats.total !== 1 ? "s" : ""} encontraron útil esto (
          {stats.helpful_percentage}%)
        </p>
      )}
    </div>
  );
}
