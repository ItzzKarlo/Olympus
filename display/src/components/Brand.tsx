import olympusLogo from "../../../assets/logo.svg";

export function Brand() {
  return (
    <div className="brand" aria-label="Olympus">
      <img className="brand__mark" src={olympusLogo} alt="" />
      <div>
        <strong>Olympus</strong>
        <span>Ambient system</span>
      </div>
    </div>
  );
}
