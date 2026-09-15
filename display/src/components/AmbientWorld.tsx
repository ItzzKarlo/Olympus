import type { SeasonalPresentation } from "../theme/seasonalTheme";

/** A fixed, bounded SVG diorama. Only small actor groups animate; no frame loop. */
function Tree({ x, y, scale = 1, bare = false }: { x: number; y: number; scale?: number; bare?: boolean }) {
  return <g transform={`translate(${x} ${y}) scale(${scale})`}>
    <path d="M0 0 3-112M2-45-30-79M3-65 34-103M2-90-15-116" fill="none" stroke="var(--world-bark)" strokeWidth="7" strokeLinecap="round" />
    {!bare && <g fill="var(--world-leaf)"><ellipse cx="-25" cy="-105" rx="38" ry="43" /><ellipse cx="26" cy="-116" rx="37" ry="49" /><ellipse cx="0" cy="-146" rx="34" ry="39" /><ellipse cx="31" cy="-93" rx="29" ry="27" fill="var(--world-leaf-light)" /></g>}
  </g>;
}

function House({ festive }: { festive: boolean }) {
  return <g className="world-house" transform="translate(115 630)">
    <path d="M0 0V-100L86-163 174-100V0Z" fill="var(--world-house)" />
    <path d="m-14-99 100-76 102 76-10 12-92-67-91 68Z" fill="var(--world-roof)" />
    <path d="M125-143v-37h19v51" fill="var(--world-roof)" />
    <g className="world-smoke" fill="none" stroke="var(--world-cloud)" strokeWidth="7" strokeLinecap="round"><path d="M136-190q-15-14 0-28t0-27" /></g>
    <g fill="var(--world-window)" stroke="var(--world-roof)" strokeWidth="4"><path d="M20-84h35v42H20ZM119-84h35v42h-35Z" /><path d="M73-119h26v25H73Z" /></g>
    <path d="M73 0v-55h28V0M37-83v40m-16-20h33m82-20v40m-16-20h33" stroke="var(--world-roof)" strokeWidth="4" fill="none" />
    {festive && <g><circle cx="87" cy="-44" r="12" fill="none" stroke="#547c61" strokeWidth="6" /><path d="m81-34 6-5 7 5" stroke="#b85552" strokeWidth="5" /><path d="M9-88q78 27 157 0" stroke="#66845b" strokeWidth="5" fill="none" /></g>}
    <path className="world-roof-snow" d="m-9-101 95-69 96 69" fill="none" stroke="#e3eaf0" strokeWidth="10" strokeLinecap="round" />
  </g>;
}

function Person({ festive, winter }: { festive: boolean; winter: boolean }) {
  return <g className="world-walker"><g transform="translate(920 665)">
    <circle cy="-43" r="7" fill="#c5a28c" /><path d="M-8-33h16l5 24h-26Z" fill="var(--world-coat)" />
    <path d="m-5-9-4 17M5-9l8 15M-8-29-9 15M8-29l13 10" stroke="var(--world-bark)" strokeWidth="4" strokeLinecap="round" />
    {winter && <path d="M-8-47q8-13 16 0M-8-34h18" stroke="#ad6660" strokeWidth="5" />}
    {festive ? <g><path d="M15-28h20v18H15Z" fill="#b65c51" /><path d="M25-28v18m-10-9h20" stroke="#e3c784" strokeWidth="3" /></g> : winter ? <g><path d="m-15-9-40 18" stroke="#827665" /><path d="M-83 8h30m-28 7h31q9 0 11-6" stroke="#a77755" strokeWidth="4" fill="none" /></g> : <path d="M16-21h9v9h-9Z" fill="#e0c48c" />}
  </g></g>;
}

export function AmbientWorld({ presentation }: { presentation: SeasonalPresentation }) {
  const festive = ["advent", "st-nicholas", "christmas", "christmas-eve"].includes(presentation.event ?? "");
  const winter = presentation.season === "winter" || festive;
  const spooky = presentation.event === "halloween";
  return <svg className="ambient-world" viewBox="0 0 1600 800" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
    <g className="world-clouds" fill="var(--world-cloud)"><path d="M65 160q-10-28 21-30 7-39 46-22 35-7 38 27 25 0 27 25Z" /><path d="M1260 110q0-22 28-24 8-32 37-22 35-10 42 25 27 0 27 21Z" /></g>
    <g className="world-plane" fill="var(--world-bark)"><path d="m0 0 32-3-15-15h7L48-4l22 2v4L48 4 24 18h-7L32 3 0 5l5-5-5-5Z" /></g>
    <path d="M0 551Q150 480 370 557T800 566T1190 536T1600 523V800H0Z" fill="var(--world-distant)" />
    <g opacity=".5"><Tree x={45} y={585} scale={.8} bare={winter || spooky} /><Tree x={360} y={586} scale={.62} bare={winter || spooky} /><Tree x={1340} y={580} scale={.9} bare={winter || spooky} /><Tree x={1490} y={566} scale={.65} bare={winter || spooky} /></g>
    <path d="M0 637Q280 589 600 658T1200 630T1600 605V800H0Z" fill="var(--world-ground)" />
    <path d="M203 622Q320 655 200 693T0 754M1590 680q-180-50-326 57t-230 63" fill="none" stroke="var(--world-path)" strokeWidth="24" />
    <House festive={festive} />
    <g fill="none" stroke="var(--world-bark)" strokeWidth="3" opacity=".5"><path d="M0 641h105m197 0h148m-440-17v39m23-42v39m24-42v39m24-42v39m239-36v39m24-39v39m24-39v39m24-39v39m24-39v39m24-39v39" /></g>
    <Tree x={45} y={710} scale={1.6} bare={winter || spooky} /><Tree x={1510} y={720} scale={1.9} bare={winter || spooky} /><Tree x={1370} y={685} scale={1.05} bare={winter || spooky} />
    <g fill="var(--world-leaf)"><path d="M0 729q20-54 49-22 26-53 59-8 26-24 41 30ZM1240 731q20-43 40-22 20-41 45-12 33-26 54 34Z" /></g>
    <g stroke="var(--world-leaf-light)" strokeWidth="3" fill="none"><path d="m300 734-7-19m7 19 9-27m-2 30 18-14m940 29-10-25m10 25 9-31m3 31 15-16" /></g>
    <g className="world-bench" stroke="var(--world-bark)" strokeWidth="5" fill="none"><path d="M1160 686h65m-62-11h59m-55 13v17m49-17v17" /></g>
    <Person winter={winter} festive={festive} />
    {presentation.season === "autumn" && !spooky && <g className="world-squirrel"><g transform="translate(340 704)" fill="#946343"><path d="M-8 0c-37-5-28-38-14-30s-10 14 15 20Z" /><ellipse rx="12" ry="8" /><circle cx="11" cy="-9" r="7" /><path d="m8-14 2-8 4 8" /><circle cx="19" cy="-1" r="4" fill="#bd9c65" /><circle cx="13" cy="-11" r="1.4" fill="#26231e" /></g></g>}
    {presentation.season === "spring" && <g fill="#d7a1b0">{[40, 72, 1305, 1340, 1420].map((x) => <g key={x}><circle cx={x} cy="719" r="6" /><circle cx={x + 8} cy="727" r="5" /></g>)}</g>}
    {presentation.event === "easter" && <g transform="translate(1280 704)"><path d="M0 0h32l-4 20H4Z" fill="#bd9266" /><path d="M4 0q12-29 24 0" fill="none" stroke="#bd9266" strokeWidth="4" /><ellipse cx="12" cy="0" rx="5" ry="8" fill="#d8a4b7" /><ellipse cx="23" cy="1" rx="5" ry="8" fill="#b7c995" /></g>}
    <g className="world-birds" fill="none" stroke="var(--world-bark)" strokeWidth="2"><path d="M1130 250q8-9 16 0 8-9 16 0m15-19q6-8 12 0 6-8 12 0" /></g>
  </svg>;
}
