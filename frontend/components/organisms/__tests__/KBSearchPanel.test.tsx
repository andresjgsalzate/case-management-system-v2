import { describe, it, expect, vi } from "vitest";
import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KBSearchPanel } from "@/components/organisms/KBSearchPanel";
import type { Filter } from "@/lib/kb-search";

function Wrapper({ initial = [] as Filter[] }: { initial?: Filter[] }) {
  const [filters, setFilters] = useState<Filter[]>(initial);
  return <KBSearchPanel filters={filters} onFiltersChange={setFilters} />;
}

describe("KBSearchPanel", () => {
  it("adds a filter when Enter is pressed", async () => {
    const onChange = vi.fn();
    render(<KBSearchPanel filters={[]} onFiltersChange={onChange} />);
    const input = screen.getByPlaceholderText(/buscar/i);
    await userEvent.type(input, "configuración{Enter}");
    expect(onChange).toHaveBeenCalledWith([
      { term: "configuración", exact: false },
    ]);
  });

  it("removes a filter when ✕ is clicked", async () => {
    const onChange = vi.fn();
    render(
      <KBSearchPanel
        filters={[
          { term: "config", exact: false },
          { term: "nginx", exact: false },
        ]}
        onFiltersChange={onChange}
      />,
    );
    const removeButtons = screen.getAllByRole("button", {
      name: /quitar filtro/i,
    });
    await userEvent.click(removeButtons[0]);
    expect(onChange).toHaveBeenCalledWith([{ term: "nginx", exact: false }]);
  });

  it("undoes the last action", async () => {
    const user = userEvent.setup();
    render(<Wrapper />);
    const input = screen.getByPlaceholderText(/buscar/i);
    await user.type(input, "uno{Enter}");
    await user.type(input, "dos{Enter}");
    // Two chips. Click Deshacer.
    const undo = screen.getByRole("button", { name: /deshacer/i });
    await user.click(undo);
    // Only "uno" remains.
    expect(screen.queryByText("dos")).not.toBeInTheDocument();
    expect(screen.getByText("uno")).toBeInTheDocument();
  });

  it("removes last chip on Backspace in empty input", async () => {
    const onChange = vi.fn();
    render(
      <KBSearchPanel
        filters={[
          { term: "a", exact: false },
          { term: "b", exact: false },
        ]}
        onFiltersChange={onChange}
      />,
    );
    const input = screen.getByPlaceholderText(/buscar/i);
    await userEvent.click(input);
    await userEvent.keyboard("{Backspace}");
    expect(onChange).toHaveBeenCalledWith([{ term: "a", exact: false }]);
  });

  it("dedupes identical filter additions silently", async () => {
    const onChange = vi.fn();
    render(
      <KBSearchPanel
        filters={[{ term: "config", exact: false }]}
        onFiltersChange={onChange}
      />,
    );
    const input = screen.getByPlaceholderText(/buscar/i);
    await userEvent.type(input, "config{Enter}");
    // onChange must NOT have been called because the filter is a duplicate.
    expect(onChange).not.toHaveBeenCalled();
    // Input must have been cleared so the user knows the action registered.
    expect(input).toHaveValue("");
  });

  it("resets the exact toggle to OFF after adding a filter", async () => {
    const user = userEvent.setup();
    render(<Wrapper />);
    const input = screen.getByPlaceholderText(/buscar/i);
    const checkbox = screen.getByRole("checkbox", { name: /exacta/i });
    await user.click(checkbox);
    expect(checkbox).toBeChecked();
    await user.type(input, "Pruebas1{Enter}");
    expect(checkbox).not.toBeChecked();
  });
});
