import Image from "next/image";

type RoboIconProps = {
  size?: number;
  opacity?: number;
  hero?: boolean;
};

export default function RoboIcon({
  size = 40,
  opacity = 1,
  hero = false,
}: RoboIconProps) {
  if (hero) {
    return (
      <Image
        src="/robot-mascot.png"
        alt="Robot"
        width={size}
        height={size}
        priority
        style={{
          width: size,
          height: "auto",
          objectFit: "contain",
          opacity,
          display: "block",
        }}
      />
    );
  }

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        overflow: "hidden",
        background: "rgba(255,255,255,.05)",
        position: "relative",
      }}
    >
      <Image
        src="/robot-mascot.png"
        alt="Robot"
        width={size}
        height={size}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "contain",
        }}
      />
    </div>
  );
}