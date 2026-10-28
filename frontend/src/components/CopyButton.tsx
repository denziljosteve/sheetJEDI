import { useState } from "react";
import { Button } from "./ui/Button";
import { useToast } from "./ui/toast-context";

interface CopyButtonProps {
  text: string;
  label?: string;
  className?: string;
}

export function CopyButton({ text, label = "Copy", className }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);
  const { push } = useToast();

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      push("Copied to clipboard", "success");
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      push("Clipboard access was blocked by the browser", "error");
    }
  };

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={handleCopy}
      className={className}
      data-testid="copy-button"
    >
      {copied ? "Copied ✓" : label}
    </Button>
  );
}
