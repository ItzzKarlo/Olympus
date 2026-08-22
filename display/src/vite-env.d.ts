/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_OLYMPUS_CORE_WS?: string;
  readonly VITE_OLYMPUS_KIOSK?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
