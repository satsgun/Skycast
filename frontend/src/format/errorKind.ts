import type { ErrorKind } from "../contract";

const ERROR_KIND_LABELS: Record<ErrorKind, string> = {
  not_found: "Location not found",
  bad_input: "Invalid input",
  provider_unreachable: "Service offline",
  internal: "Something went wrong",
};

export function errorKindLabel(kind: ErrorKind): string {
  return ERROR_KIND_LABELS[kind];
}

const SYSTEM_ERROR_KINDS: Record<ErrorKind, boolean> = {
  not_found: false,
  bad_input: false,
  provider_unreachable: true,
  internal: true,
};

export function isSystemError(kind: ErrorKind): boolean {
  return SYSTEM_ERROR_KINDS[kind];
}
