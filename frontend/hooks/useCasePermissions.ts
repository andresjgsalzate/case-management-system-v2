"use client";

import { useAuthStore } from "@/store/auth.store";
import type { Case, CasePermissions, UserPermission } from "@/lib/types";

function scopeFor(permissions: UserPermission[] | undefined, action: string): "none" | "own" | "team" | "all" {
  if (!permissions) return "none";
  const p = permissions.find((x) => x.module === "cases" && x.action === action);
  if (!p) return "none";
  if (p.scope === "all") return "all";
  if (p.scope === "team") return "team";
  return "own";
}

/** Mirror of check_case_action (backend/src/core/permissions/case_permissions.py). */
export function useCasePermissions(c: Case | undefined): CasePermissions {
  const user = useAuthStore((s) => s.user);
  const empty: CasePermissions = {
    canRead: false, canUpdate: false, canTransition: false,
    canTransfer: false, canComment: false, canAttach: false,
  };
  if (!user || !c) return empty;

  const userId = user.id;
  const userTeamId = user.team_id ?? null;
  const userLevel = user.role_level ?? 1;
  const isReporter = userLevel === 0;
  const isAsignee = c.assigned_to === userId;
  const isCreator = c.created_by === userId;
  const sameTeam = !!c.team_id && c.team_id === userTeamId;
  const archived = c.is_archived;

  const readScope = scopeFor(user.permissions, "read");
  const updateScope = scopeFor(user.permissions, "update");
  const transitionScope = scopeFor(user.permissions, "transition");

  const canRead =
    readScope === "all" ||
    isCreator || isAsignee ||
    (readScope === "team" && sameTeam);

  const canComment = canRead && !archived;
  const canAttach = canComment;

  let canUpdate = false;
  if (!isReporter && !archived) {
    if (updateScope === "all") canUpdate = true;
    else if (updateScope === "team" && sameTeam) canUpdate = true;
    else if (isAsignee) canUpdate = true;
  }

  let canTransition = false;
  if (!isReporter && !archived) {
    if (transitionScope === "all") canTransition = true;
    else if (isAsignee) canTransition = true;
    else if (transitionScope === "team" && sameTeam && userLevel > c.current_level) canTransition = true;
  }

  let canTransfer = false;
  if (!isReporter && !archived) {
    if (updateScope === "all") canTransfer = true;
    else if (isAsignee) canTransfer = true;
    else if (updateScope === "team" && sameTeam && userLevel >= c.current_level) canTransfer = true;
  }

  return { canRead, canUpdate, canTransition, canTransfer, canComment, canAttach };
}
