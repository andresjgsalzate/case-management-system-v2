import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";

import { AlertReportTemplateEditor } from "@/components/organisms/alert_reports/AlertReportTemplateEditor";
import type {
  AlertReportTemplate,
  AlertReportTemplateVersion,
} from "@/lib/types";


function makeTemplate(): AlertReportTemplate {
  return {
    id: "tpl-1",
    tenant_id: null,
    name: "SOC standard",
    code: "soc_standard",
    description: null,
    current_version_id: "v-1",
    current_version_number: 1,
    is_default: true,
    is_active: true,
    created_at: "2026-05-17T10:00:00Z",
    updated_at: "2026-05-17T10:00:00Z",
  };
}

function makeVersion(): AlertReportTemplateVersion {
  return {
    id: "v-1",
    template_id: "tpl-1",
    version: 1,
    name_snapshot: "SOC standard",
    header_config: {},
    footer_config: {},
    blocks: [
      { type: "alert_metadata", params: {} },
      { type: "evidence_grid", params: { include_iocs: true } },
    ],
    css_overrides: null,
    created_by_user_id: null,
    created_at: "2026-05-17T10:00:00Z",
    change_summary: null,
  };
}


describe("AlertReportTemplateEditor", () => {
  it("renders blocks in order from initialVersion", () => {
    render(
      <AlertReportTemplateEditor
        template={makeTemplate()}
        initialVersion={makeVersion()}
        onSave={vi.fn()}
      />,
    );
    const blockHeadings = screen.getAllByText(
      /^\d+\. (alert_metadata|evidence_grid)$/,
    );
    expect(blockHeadings).toHaveLength(2);
    expect(blockHeadings[0]).toHaveTextContent("1. alert_metadata");
    expect(blockHeadings[1]).toHaveTextContent("2. evidence_grid");
  });

  it("removes a block when the ✕ button is clicked", async () => {
    render(
      <AlertReportTemplateEditor
        template={makeTemplate()}
        initialVersion={makeVersion()}
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByText("1. alert_metadata")).toBeInTheDocument();
    expect(screen.getByText("2. evidence_grid")).toBeInTheDocument();

    const removeButtons = screen.getAllByRole("button", {
      name: /eliminar/i,
    });
    await userEvent.click(removeButtons[0]);

    expect(
      screen.queryByText("1. alert_metadata"),
    ).not.toBeInTheDocument();
    // evidence_grid is now position 1
    expect(screen.getByText("1. evidence_grid")).toBeInTheDocument();
  });

  it("moves a block down when ▼ is clicked", async () => {
    render(
      <AlertReportTemplateEditor
        template={makeTemplate()}
        initialVersion={makeVersion()}
        onSave={vi.fn()}
      />,
    );
    const downButtons = screen.getAllByRole("button", {
      name: /mover abajo/i,
    });
    // Click the first one (moves alert_metadata down → swaps with evidence_grid)
    await userEvent.click(downButtons[0]);

    const blockHeadings = screen.getAllByText(
      /^\d+\. (alert_metadata|evidence_grid)$/,
    );
    expect(blockHeadings[0]).toHaveTextContent("1. evidence_grid");
    expect(blockHeadings[1]).toHaveTextContent("2. alert_metadata");
  });

  it("calls onSave when the Guardar button is pressed", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <AlertReportTemplateEditor
        template={makeTemplate()}
        initialVersion={makeVersion()}
        onSave={onSave}
      />,
    );
    const saveBtn = screen.getByRole("button", { name: /guardar/i });
    await userEvent.click(saveBtn);
    expect(onSave).toHaveBeenCalledTimes(1);
    const payload = onSave.mock.calls[0][0];
    expect(payload.name).toBe("SOC standard");
    expect(payload.blocks).toHaveLength(2);
  });
});
