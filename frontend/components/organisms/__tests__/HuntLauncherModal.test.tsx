import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import { HuntLauncherModal } from "@/components/organisms/forensic/HuntLauncherModal";

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

describe("HuntLauncherModal", () => {
  it("renders nothing when isOpen is false", () => {
    const { container } = renderWithQuery(
      <HuntLauncherModal
        caseId="case-1"
        isOpen={false}
        onClose={vi.fn()}
        onLaunched={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders the modal header when isOpen is true", () => {
    renderWithQuery(
      <HuntLauncherModal
        caseId="case-1"
        isOpen={true}
        onClose={vi.fn()}
        onLaunched={vi.fn()}
      />,
    );
    expect(screen.getByText("Lanzar hunt forense")).toBeInTheDocument();
    expect(screen.getByText("1. Seleccionar artifact")).toBeInTheDocument();
  });

  it("disables the launch button before an artifact is picked", () => {
    renderWithQuery(
      <HuntLauncherModal
        caseId="case-1"
        isOpen={true}
        onClose={vi.fn()}
        onLaunched={vi.fn()}
      />,
    );
    const launch = screen.getByRole("button", { name: /lanzar hunt/i });
    expect(launch).toBeDisabled();
  });
});
