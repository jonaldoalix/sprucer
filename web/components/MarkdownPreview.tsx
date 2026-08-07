"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Props = {
  content: string;
  className?: string;
};

/** Render generation markdown as readable preview (not raw source). */
export function MarkdownPreview({ content, className }: Props) {
  return (
    <div className={["md-preview", className].filter(Boolean).join(" ")}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
