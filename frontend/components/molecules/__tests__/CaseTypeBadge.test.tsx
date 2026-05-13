import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CaseTypeBadge } from "@/components/molecules/CaseTypeBadge";

describe("CaseTypeBadge", () => {
  it.each([
    ["request", "Solicitud"],
    ["incident", "Incidencia"],
    ["event", "Evento"],
  ] as const)("renders Spanish label for %s", (type, expected) => {
    render(<CaseTypeBadge caseType={type} />);
    expect(screen.getByText(expected)).toBeInTheDocument();
  });
});
