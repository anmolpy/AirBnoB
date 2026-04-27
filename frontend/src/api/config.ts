const DEFAULT_API_BASE_URL = "http://localhost:5000";

type ImportMetaEnvLike = {
  VITE_API_BASE_URL?: string;
};

type ImportMetaLike = {
  env?: ImportMetaEnvLike;
};

function readImportMetaEnv(): ImportMetaEnvLike | undefined {
  try {
    return (import.meta as ImportMetaLike | undefined)?.env;
  } catch {
    return undefined;
  }
}

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

export function getApiBaseUrl(): string {
  const importMetaEnv = readImportMetaEnv();
  const explicitBaseUrl = importMetaEnv?.VITE_API_BASE_URL;

  if (explicitBaseUrl && explicitBaseUrl.trim().length > 0) {
    return trimTrailingSlash(explicitBaseUrl);
  }

  if (typeof window !== "undefined" && window.location?.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:5000`;
  }

  return DEFAULT_API_BASE_URL;
}

export const API_BASE_URL = getApiBaseUrl();
