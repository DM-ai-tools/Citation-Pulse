"use client";

import { useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { apiClient, type ApiClientOptions } from "@/services/apiClient";

export function useAuthApi() {
  const { getToken } = useAuth();

  return useCallback(
    (path: string, init: ApiClientOptions = {}) => apiClient(path, { ...init, getToken }),
    [getToken],
  );
}
