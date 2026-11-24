// Purpose: Render the reusable brand logo interface and keep its presentation and interactions together.
import logo from "../assets/lankapex-logo.png";

// Render the brand logo interface and connect its controls to the state and callbacks defined here.
export default function BrandLogo({ className = "", tone = "light", alt = "LankaPex — Business Connects Everyone" }) {
  const imageStyle = { position: "absolute", width: "126%", maxWidth: "none", height: "auto", top: 0, left: 0, margin: "-5.5% 0 0 -12.5%" };
  return (
    <div
      className={className}
      style={{ position: "relative", width: 280, maxWidth: "100%", aspectRatio: "3.5", overflow: "hidden" }}
    >
      <img
        src={logo}
        alt={alt}
        width="2172"
        height="724"
        style={imageStyle}
      />
      {tone === "dark" && <img
        src={logo}
        alt=""
        aria-hidden="true"
        width="2172"
        height="724"
        style={{ ...imageStyle, filter: "brightness(0) invert(1)", clipPath: "polygon(28% 0, 65.5% 0, 65.5% 65%, 100% 65%, 100% 100%, 28% 100%)" }}
      />}
    </div>
  );
}
