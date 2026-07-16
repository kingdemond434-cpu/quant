import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const fmt = {
  num: (v: number, d = 2) =>
    v.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d }),
  int: (v: number) => Math.round(v).toLocaleString(),
  pct: (v: number, d = 1) => `${(v * 100).toFixed(d)}%`,
  money: (v: number) =>
    `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
};
