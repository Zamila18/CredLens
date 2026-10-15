/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Where the API lives, seen from the browser. Default "/api". */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
