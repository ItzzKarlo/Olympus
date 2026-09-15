import { memo, type CSSProperties } from "react";

import type { SeasonalPresentation } from "../theme/seasonalTheme";

import { AmbientWorld } from "./AmbientWorld";

interface SeasonalEnvironmentProps {
  retreat?: boolean;
  night?: boolean;
  mode: string;
  presentation: SeasonalPresentation;
}

const CHRISTMAS_EVENTS = new Set([
  "advent",
  "st-nicholas",
  "christmas-eve",
  "christmas",
]);

const SUBTLE_MODES = new Set(["development", "gaming", "matchday", "media", "news"]);

const SNOWFLAKES = Array.from({ length: 24 }, (_, index) => index);
const LEAVES = Array.from({ length: 12 }, (_, index) => index);
const PETALS = Array.from({ length: 10 }, (_, index) => index);
const BATS = Array.from({ length: 3 }, (_, index) => index);
const TOP_LIGHTS = Array.from({ length: 25 }, (_, index) => index);
const SIDE_LIGHTS = Array.from({ length: 10 }, (_, index) => index);
const ORNAMENTS = Array.from({ length: 14 }, (_, index) => index);
const FLOWERS = Array.from({ length: 11 }, (_, index) => index);
const EGGS = Array.from({ length: 7 }, (_, index) => index);

function seeded(index: number, salt: number): number {
  const value = Math.sin(index * 83.173 + salt * 19.371) * 43758.5453;
  return value - Math.floor(value);
}

function customStyle(values: Record<string, string | number>): CSSProperties {
  return values as CSSProperties;
}

function SnowLayer({ dense = false }: { dense?: boolean }) {
  const flakes = dense ? SNOWFLAKES : SNOWFLAKES.slice(0, 24);
  return (
    <div className="season-env__snow" aria-hidden="true">
      {flakes.map((index) => (
        <span
          key={index}
          style={customStyle({
            "--snow-left": `${seeded(index, 1) * 100}%`,
            "--snow-delay": `${-seeded(index, 2) * 18}s`,
            "--snow-duration": `${10 + seeded(index, 3) * 12}s`,
            "--snow-drift": `${-3 + seeded(index, 4) * 6}rem`,
            "--snow-scale": 0.45 + seeded(index, 5) * 1.05,
            "--snow-opacity": 0.3 + seeded(index, 6) * 0.62,
          })}
        />
      ))}
    </div>
  );
}

function Snowbanks() {
  return <div className="season-env__snowbanks" aria-hidden="true" />;
}

function Fireworks() {
  return (
    <div className="season-env__fireworks" aria-hidden="true">
      <span className="firework firework--one" />
      <span className="firework firework--two" />
      <span className="firework firework--three" />
    </div>
  );
}

function ChristmasLights() {
  return (
    <div className="christmas-lights" aria-hidden="true">
      <div className="christmas-lights__wire christmas-lights__wire--top">
        {TOP_LIGHTS.map((index) => <span key={index} className={`bulb bulb--${index % 5}`} />)}
      </div>
      <div className="christmas-lights__wire christmas-lights__wire--left">
        {SIDE_LIGHTS.map((index) => <span key={index} className={`bulb bulb--${(index + 2) % 5}`} />)}
      </div>
      <div className="christmas-lights__wire christmas-lights__wire--right">
        {SIDE_LIGHTS.map((index) => <span key={index} className={`bulb bulb--${(index + 4) % 5}`} />)}
      </div>
    </div>
  );
}

function ChristmasTree() {
  return (
    <div className="christmas-tree" aria-hidden="true">
      <span className="christmas-tree__star">★</span>
      <span className="christmas-tree__tier christmas-tree__tier--top" />
      <span className="christmas-tree__tier christmas-tree__tier--middle" />
      <span className="christmas-tree__tier christmas-tree__tier--bottom" />
      <span className="christmas-tree__garland christmas-tree__garland--one" />
      <span className="christmas-tree__garland christmas-tree__garland--two" />
      <span className="christmas-tree__trunk" />
      {ORNAMENTS.map((index) => (
        <span
          className={`christmas-tree__ornament ornament--${index % 4}`}
          key={index}
          style={customStyle({
            "--ornament-left": `${25 + seeded(index, 11) * 50}%`,
            "--ornament-top": `${29 + seeded(index, 12) * 56}%`,
            "--ornament-scale": 0.68 + seeded(index, 13) * 0.65,
          })}
        />
      ))}
    </div>
  );
}

function Snowman() {
  return (
    <div className="snowman" aria-hidden="true">
      <span className="snowman__hat" />
      <span className="snowman__head"><i /><i /><b /></span>
      <span className="snowman__scarf" />
      <span className="snowman__body snowman__body--middle"><i /><i /></span>
      <span className="snowman__body snowman__body--bottom" />
      <span className="snowman__arm snowman__arm--left" />
      <span className="snowman__arm snowman__arm--right" />
    </div>
  );
}

function ChristmasEnvironment() {
  return (
    <>
      <div className="season-env__winter-glow" />
      <ChristmasLights />
      <SnowLayer dense />
      <ChristmasTree />
      <Snowman />
      <div className="christmas-gifts" aria-hidden="true">
        <span className="gift gift--one" /><span className="gift gift--two" /><span className="gift gift--three" />
      </div>
      <Snowbanks />
    </>
  );
}

function Pumpkin({ className = "" }: { className?: string }) {
  return (
    <div className={`pumpkin ${className}`} aria-hidden="true">
      <span className="pumpkin__stem" />
      <span className="pumpkin__ridge pumpkin__ridge--left" />
      <span className="pumpkin__ridge pumpkin__ridge--right" />
      <span className="pumpkin__eye pumpkin__eye--left" />
      <span className="pumpkin__eye pumpkin__eye--right" />
      <span className="pumpkin__mouth" />
    </div>
  );
}

function Scarecrow() {
  return (
    <div className="scarecrow" aria-hidden="true">
      <span className="scarecrow__hat" />
      <span className="scarecrow__head"><i /><i /><b /></span>
      <span className="scarecrow__arm scarecrow__arm--left" />
      <span className="scarecrow__arm scarecrow__arm--right" />
      <span className="scarecrow__body" />
      <span className="scarecrow__post" />
    </div>
  );
}

function HalloweenEnvironment() {
  return (
    <>
      <div className="halloween-moon" aria-hidden="true" />
      <div className="spider-web spider-web--left" aria-hidden="true" />
      <div className="spider-web spider-web--right" aria-hidden="true" />
      <div className="bat-flight" aria-hidden="true">
        {BATS.map((index) => (
          <span
            key={index}
            style={customStyle({
              "--bat-top": `${8 + seeded(index, 21) * 48}%`,
              "--bat-delay": `${-seeded(index, 22) * 16}s`,
              "--bat-duration": `${12 + seeded(index, 23) * 13}s`,
              "--bat-scale": 0.65 + seeded(index, 24) * 0.85,
            })}
          ><svg viewBox="0 0 40 20" width="40" height="20"><path d="M20 9 15 2l-2 4L0 0l5 14 8-3 7 9 7-9 8 3L40 0 27 6l-2-4Z" fill="currentColor" /></svg></span>
        ))}
      </div>
      <div className="halloween-fence" aria-hidden="true" />
      <Pumpkin className="pumpkin--left pumpkin--large" />
      <Pumpkin className="pumpkin--left-two pumpkin--small" />
      <Pumpkin className="pumpkin--right pumpkin--medium" />
      <Scarecrow />
      <div className="halloween-fog" aria-hidden="true"><i /><i /><i /></div>
    </>
  );
}

function AutumnEnvironment({ stMartin }: { stMartin: boolean }) {
  return (
    <>
      <div className="autumn-haze" aria-hidden="true" />
      <div className="leaf-gusts" aria-hidden="true">
        {LEAVES.map((index) => (
          <span
            className={`leaf leaf--${index % 5}`}
            key={index}
            style={customStyle({
              "--leaf-top": `${5 + seeded(index, 31) * 78}%`,
              "--leaf-delay": `${-seeded(index, 32) * 18}s`,
              "--leaf-duration": `${9 + seeded(index, 33) * 13}s`,
              "--leaf-scale": 0.55 + seeded(index, 34) * 0.9,
              "--leaf-rotate": `${seeded(index, 35) * 220 - 110}deg`,
            })}
          />
        ))}
      </div>
      <div className="leaf-pile leaf-pile--left" aria-hidden="true" />
      <div className="leaf-pile leaf-pile--right" aria-hidden="true" />
      {stMartin ? <div className="martin-lantern" aria-hidden="true"><span /><i /></div> : null}
    </>
  );
}

function SpringEnvironment({ easter }: { easter: boolean }) {
  return (
    <>
      <div className="spring-branch spring-branch--left" aria-hidden="true"><i /><i /><i /><i /></div>
      <div className="spring-branch spring-branch--right" aria-hidden="true"><i /><i /><i /></div>
      <div className="spring-petals" aria-hidden="true">
        {PETALS.map((index) => (
          <span key={index} style={customStyle({
            "--petal-left": `${seeded(index, 41) * 100}%`,
            "--petal-delay": `${-seeded(index, 42) * 16}s`,
            "--petal-duration": `${10 + seeded(index, 43) * 12}s`,
            "--petal-scale": 0.55 + seeded(index, 44) * 0.8,
          })} />
        ))}
      </div>
      <div className="spring-meadow" aria-hidden="true">
        {FLOWERS.map((index) => <span key={index} className={`spring-flower spring-flower--${index % 4}`} />)}
      </div>
      {easter ? (
        <div className="easter-scene" aria-hidden="true">
          <span className="easter-bunny"><i /><i /></span>
          {EGGS.map((index) => <span key={index} className={`easter-egg easter-egg--${index % 4}`} />)}
        </div>
      ) : null}
    </>
  );
}

function SummerEnvironment() {
  return (
    <>
      <div className="summer-sun" aria-hidden="true"><span /></div>
      <div className="summer-cloud summer-cloud--one" aria-hidden="true" />
      <div className="summer-cloud summer-cloud--two" aria-hidden="true" />
      <div className="summer-meadow" aria-hidden="true"><i /><i /><i /><i /><i /></div>
      <div className="summer-fireflies" aria-hidden="true"><i /><i /><i /><i /><i /><i /></div>
    </>
  );
}

function WinterEnvironment({ fireworks }: { fireworks: boolean }) {
  return (
    <>
      <div className="season-env__winter-glow" />
      <SnowLayer />
      <Snowman />
      <Snowbanks />
      {fireworks ? <Fireworks /> : null}
    </>
  );
}

export const SeasonalEnvironment = memo(function SeasonalEnvironment({ mode, presentation, retreat = false, night = false }: SeasonalEnvironmentProps) {
  const subtle = SUBTLE_MODES.has(mode);
  const event = presentation.event;
  let content;

  if (event && CHRISTMAS_EVENTS.has(event)) {
    content = <ChristmasEnvironment />;
  } else if (event === "halloween") {
    content = <HalloweenEnvironment />;
  } else if (presentation.season === "autumn") {
    content = <AutumnEnvironment stMartin={event === "st-martin"} />;
  } else if (presentation.season === "spring") {
    content = <SpringEnvironment easter={event === "easter"} />;
  } else if (presentation.season === "summer") {
    content = <SummerEnvironment />;
  } else {
    content = <WinterEnvironment fireworks={event === "new-year" || event === "new-years-eve"} />;
  }

  return (
    <div
      className={`seasonal-environment seasonal-environment--${subtle ? "subtle" : "immersive"} environment-${event ?? presentation.season}`}
      data-intensity={retreat ? "retreat" : ["gaming", "matchday", "news"].includes(mode) ? "minimal" : subtle ? "reduced" : night || mode === "night" ? "calm" : "full"}
      data-night={night || mode === "night"}
      data-season={presentation.season}
      data-seasonal-event={event ?? undefined}
      aria-hidden="true"
    >
      <AmbientWorld presentation={presentation} />
      {content}
    </div>
  );
}, (before, after) => before.mode === after.mode && before.presentation.id === after.presentation.id && before.retreat === after.retreat && before.night === after.night);
