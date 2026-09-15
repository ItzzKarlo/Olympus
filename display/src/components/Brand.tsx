export function Brand() {
  return (
    <div className="brand" aria-label="Olympus">
      <svg className="brand__mark" viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <path d="M5 35 19 11l9 15 5-8 10 17H5Z" stroke="var(--logo-primary)" strokeWidth="3" strokeLinejoin="round" />
        <path d="M17 35 24 23M10 42h28" stroke="var(--logo-secondary)" strokeWidth="3" strokeLinecap="round" />
      </svg>
      <div><strong>Olympus</strong><span>Ambient system</span></div>
    </div>
  );
}
