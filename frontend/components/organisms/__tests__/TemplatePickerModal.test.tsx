import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";

import { TemplatePickerModal } from "@/components/organisms/alert_reports/TemplatePickerModal";

vi.mock("@/hooks/useAlertReportTemplates", () => ({
  useAlertReportTemplates: () => ({
    data: [
      {
        id: "tpl-1", tenant_id: null, name: "SOC standard",
        code: "soc_standard", description: "Default global",
        current_version_id: "v-1", current_version_number: 3,
        is_default: true, is_active: true,
        created_at: "2026-05-17T10:00:00Z",
        updated_at: "2026-05-17T10:00:00Z",
      },
      {
        id: "tpl-2", tenant_id: null, name: "Executive brief",
        code: "executive_brief", description: null,
        current_version_id: "v-2", current_version_number: 1,
        is_default: false, is_active: true,
        created_at: "2026-05-17T10:00:00Z",
        updated_at: "2026-05-17T10:00:00Z",
      },
      {
        id: "tpl-3", tenant_id: null, name: "Old archived",
        code: "old_archived", description: null,
        current_version_id: "v-3", current_version_number: 1,
        is_default: false, is_active: false,  // filtered out
        created_at: "2026-05-17T10:00:00Z",
        updated_at: "2026-05-17T10:00:00Z",
      },
    ],
    isLoading: false,
  }),
}));


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


describe("TemplatePickerModal", () => {
  it("renders nothing when closed", () => {
    const { container } = renderWithQuery(
      <TemplatePickerModal
        isOpen={false}
        caseId="c1"
        onClose={vi.fn()}
        onSelected={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("lists active templates with default highlighted", () => {
    renderWithQuery(
      <TemplatePickerModal
        isOpen={true}
        caseId="c1"
        onClose={vi.fn()}
        onSelected={vi.fn()}
      />,
    );
    expect(screen.getByText("SOC standard")).toBeInTheDocument();
    expect(screen.getByText("Executive brief")).toBeInTheDocument();
    // Inactive template should NOT appear
    expect(screen.queryByText("Old archived")).not.toBeInTheDocument();
    // Default badge present (the ⭐ Default chip — distinct from the
    // "Default global" description text)
    expect(screen.getByText("⭐ Default")).toBeInTheDocument();
  });

  it("calls onSelected with the chosen template id", async () => {
    const onSelected = vi.fn();
    renderWithQuery(
      <TemplatePickerModal
        isOpen={true}
        caseId="c1"
        onClose={vi.fn()}
        onSelected={onSelected}
      />,
    );
    // The default (tpl-1) is preselected; pick Executive brief instead
    const executiveLabel = screen.getByText("Executive brief")
      .closest("label");
    expect(executiveLabel).not.toBeNull();
    await userEvent.click(executiveLabel!);
    await userEvent.click(
      screen.getByRole("button", { name: /generar pdf/i }),
    );
    expect(onSelected).toHaveBeenCalledWith("tpl-2");
  });
});
