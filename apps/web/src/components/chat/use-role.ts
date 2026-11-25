"use client";

import { useCallback, useEffect, useState } from "react";

import { DEFAULT_ROLE, isRole, ROLE_STORAGE_KEY, type RoleId } from "@/lib/recruiter";

const EVENT = "provenance-role-change";

/** The visitor's recruiter-mode role, kept in this browser only. Never sent to the API. */
export function useRole(): [RoleId, (role: RoleId) => void] {
  const [role, setRoleState] = useState<RoleId>(DEFAULT_ROLE);

  useEffect(() => {
    const read = () => {
      try {
        const saved = localStorage.getItem(ROLE_STORAGE_KEY);
        setRoleState(isRole(saved) ? saved : DEFAULT_ROLE);
      } catch {
        // Storage unavailable: keep the default.
      }
    };
    read();
    window.addEventListener(EVENT, read);
    return () => window.removeEventListener(EVENT, read);
  }, []);

  const setRole = useCallback((next: RoleId) => {
    try {
      localStorage.setItem(ROLE_STORAGE_KEY, next);
    } catch {
      // Storage unavailable: the choice lasts for this page only.
    }
    setRoleState(next);
    window.dispatchEvent(new Event(EVENT));
  }, []);

  return [role, setRole];
}
