"use client";

import { ChevronDown, ChevronRight, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { useTaxonomyTree } from "@/hooks/useSecurityTaxonomies";
import type { SecurityTaxonomyTreeNode } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TaxonomyTreeViewProps {
  selectedId: string | null;
  onSelect: (node: SecurityTaxonomyTreeNode) => void;
  /** Show inactive nodes too (default false). */
  includeInactive?: boolean;
}

export function TaxonomyTreeView({
  selectedId,
  onSelect,
  includeInactive = false,
}: TaxonomyTreeViewProps) {
  const { data, isLoading, error } = useTaxonomyTree(includeInactive);
  const [search, setSearch] = useState("");
  const [onlyOverrides, setOnlyOverrides] = useState(false);

  const filtered = useMemo(() => {
    if (!data) return [] as SecurityTaxonomyTreeNode[];
    return filterTree(data, search.trim().toLowerCase(), onlyOverrides);
  }, [data, search, onlyOverrides]);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b p-2 space-y-2">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Buscar..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded border bg-background py-1 pl-7 pr-2 text-sm"
          />
        </div>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={onlyOverrides}
            onChange={(e) => setOnlyOverrides(e.target.checked)}
          />
          Solo overrides
        </label>
      </div>

      <div className="flex-1 overflow-y-auto p-1">
        {isLoading ? (
          <p className="p-2 text-xs text-muted-foreground">Cargando...</p>
        ) : error ? (
          <p className="p-2 text-xs text-red-600">
            Error: {(error as Error).message}
          </p>
        ) : filtered.length === 0 ? (
          <p className="p-2 text-xs text-muted-foreground">
            No hay taxonomías para mostrar.
          </p>
        ) : (
          <ul role="tree" className="space-y-0.5">
            {filtered.map((node) => (
              <TreeNode
                key={node.id}
                node={node}
                depth={0}
                selectedId={selectedId}
                onSelect={onSelect}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

interface TreeNodeProps {
  node: SecurityTaxonomyTreeNode;
  depth: number;
  selectedId: string | null;
  onSelect: (node: SecurityTaxonomyTreeNode) => void;
}

function TreeNode({ node, depth, selectedId, onSelect }: TreeNodeProps) {
  const [expanded, setExpanded] = useState(depth < 1);
  const hasChildren = node.children.length > 0;
  const isSelected = node.id === selectedId;
  const isOverride = node.tenant_id !== null;

  return (
    <li role="treeitem" aria-selected={isSelected}>
      <div
        className={cn(
          "flex items-center gap-1 rounded px-1 py-0.5 cursor-pointer hover:bg-muted/60",
          isSelected && "bg-blue-100 dark:bg-blue-950/40",
        )}
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
        onClick={() => onSelect(node)}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
            className="rounded p-0.5 hover:bg-muted"
            aria-label={expanded ? "Colapsar" : "Expandir"}
          >
            {expanded ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </button>
        ) : (
          <span className="inline-block w-4" />
        )}
        <span
          className={cn(
            "flex-1 truncate text-sm",
            !node.is_active && "italic text-muted-foreground line-through",
          )}
          title={node.name}
        >
          <span className="font-mono text-xs text-muted-foreground">
            {node.tuic_code}
          </span>{" "}
          <span>— {node.name}</span>
          {isOverride ? (
            <span className="ml-1 text-[10px] text-purple-600 dark:text-purple-400">
              override
            </span>
          ) : null}
        </span>
      </div>
      {hasChildren && expanded ? (
        <ul role="group" className="space-y-0.5">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function filterTree(
  nodes: SecurityTaxonomyTreeNode[],
  search: string,
  onlyOverrides: boolean,
): SecurityTaxonomyTreeNode[] {
  // Filter recursively: include node if it matches OR any descendant matches.
  const out: SecurityTaxonomyTreeNode[] = [];
  for (const node of nodes) {
    const childMatches = filterTree(node.children, search, onlyOverrides);
    const selfMatches = nodeMatches(node, search, onlyOverrides);
    if (selfMatches || childMatches.length > 0) {
      out.push({ ...node, children: childMatches });
    }
  }
  return out;
}

function nodeMatches(
  node: SecurityTaxonomyTreeNode,
  search: string,
  onlyOverrides: boolean,
): boolean {
  if (onlyOverrides && node.tenant_id === null) return false;
  if (!search) return true;
  return (
    node.tuic_code.toLowerCase().includes(search) ||
    node.name.toLowerCase().includes(search)
  );
}
