/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_OLYMPUS_CORE_WS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
