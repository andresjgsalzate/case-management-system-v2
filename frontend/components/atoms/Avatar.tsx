import { HTMLAttributes } from "react";
import { cn, getInitials } from "@/lib/utils";

type AvatarSize = "xs" | "sm" | "md" | "lg";

interface AvatarProps extends HTMLAttributes<HTMLDivElement> {
  name: string;
  src?: string | null;
  size?: AvatarSize;
}

const sizes: Record<AvatarSize, string> = {
  xs: "h-6 w-6 text-[10px]",
  sm: "h-8 w-8 text-xs",
  md: "h-9 w-9 text-sm",
  lg: "h-11 w-11 text-base",
};

// Deterministic color from name
const COLORS = [
  "bg-blue-500",
  "bg-violet-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-rose-500",
  "bg-cyan-500",
  "bg-indigo-500",
  "bg-pink-500",
];

function colorForName(name: string): string {
  const idx = name.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0) % COLORS.length;
  return COLORS[idx];
}

export function Avatar({ name, src, size = "md", className, ...props }: AvatarProps) {
  const initials = getInitials(name);
  const color = colorForName(name);

  if (src) {
    return (
      <div className={cn("rounded-full overflow-hidden shrink-0", sizes[size], className)} {...props}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt={name} className="h-full w-full object-cover" />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-full flex items-center justify-center shrink-0 font-medium text-white select-none",
        sizes[size],
        color,
        className
      )}
      title={name}
      {...props}
    >
      {initials}
    </div>
  );
}
