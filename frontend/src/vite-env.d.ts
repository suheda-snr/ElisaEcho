/// <reference types="vite/client" />

// Only VITE_-prefixed variables reach the browser bundle. Never put secrets here.
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
