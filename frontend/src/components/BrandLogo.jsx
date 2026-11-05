import logo from "../assets/lankapex-logo.png";

export default function BrandLogo({ className = "" }) {
  return (
    <div
      className={className}
      style={{ position: "relative", width: 280, maxWidth: "100%", aspectRatio: "3.5", overflow: "hidden" }}
    >
      <img
        src={logo}
        alt="LankaPex — Business Connects Everyone"
        width="2172"
        height="724"
        style={{ position: "absolute", width: "126%", maxWidth: "none", height: "auto", top: 0, left: 0, margin: "-5.5% 0 0 -12.5%" }}
      />
    </div>
  );
}
