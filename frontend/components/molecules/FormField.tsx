import { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

interface FormFieldProps extends HTMLAttributes<HTMLDivElement> {
  label: string;
  htmlFor?: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}

export function FormField({
  label,
  htmlFor,
  error,
  hint,
  required,
  children,
  className,
  ...props
}: FormFieldProps) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)} {...props}>
      <label
        htmlFor={htmlFor}
        className="text-sm font-medium text-foreground leading-none"
      >
        {label}
        {required && <span className="text-destructive ml-0.5">*</span>}
      </label>
      {children}
      {hint && !error && (
        <p className="text-xs text-muted-foreground">{hint}</p>
      )}
      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}
    </div>
  );
}
