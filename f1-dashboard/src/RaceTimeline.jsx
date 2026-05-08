import { useState } from 'react';

export default function RaceTimeline({ logs }) {
  const [activePhase, setActivePhase] = useState(0);

  const phases = [
    {
      id: 0,
      title: "Laps 1 - 10",
      subtitle: "The Thermal Shock & Heavy-Fuel Survival",
      desc: "As the lights went out for the 2026 Miami Grand Prix, internet forums were already abuzz with reports of brutal track temperatures exceeding 55 degrees Celsius. Under the new regulations, which shifted the power unit dependency to a 50/50 split between internal combustion and electrical power, the opening phase became a tense game of thermal chess.",
      desc2: "With cars carrying heavy starting fuel loads (100kg+), the immense weight pushed tire carcass temperatures instantly toward their blistering point. To combat this, veterans immediately deployed extreme Lift & Coast tactics at the end of the long straights. As shown in the telemetry distribution below, Alonso and Verstappen sacrificed massive amounts of raw lap time to protect their brakes and manage battery State of Charge.",
      desc3: "While Alonso focused on survival, George Russell weaponized the Mercedes power unit, clocking 333 km/h in the speed traps, though his high variance suggested he was stuck in a brutal DRS train. Further back, Williams and Haas ran extreme low-drag setups to survive the midfield straights; Alex Albon and Oliver Bearman both clocked 327 km/h, boasting high S1/S3 ratios (1.293 and 1.282) which indicated they were completely sacrificing Sector 3 cornering downforce to stay competitive in Sector 1.",
      contextTitle: "Telemetry Context: Lift & Coast Mechanics",
      contextDesc: "Lift and Coast (L&C) involves releasing the accelerator pedal significantly before the optimal braking point. In the 2026 regulations, this is critical not just for fuel saving, but for cooling the MGU-K and preventing brake caliper thermal runaway. Alonso's extreme 1.52s metric indicates that critical thermal limits were breached almost immediately, forcing an extreme management map.",
      stats: [
        { label: "ALO Lift & Coast", val: "1.52s/lap" },
        { label: "ALB Top Speed", val: "327 km/h" },
        { label: "Track Evolution", val: "0.000s" }
      ],
      logRange: [0, 10]
    },
    {
      id: 1,
      title: "Laps 11 - 25",
      subtitle: "The Strategic Anomaly of Lance Stroll",
      desc: "As the medium tires began to degredate heavily across the field, the pit window violently swung open. Several drivers reported severe rear thermal degradation. The 2026 active aerodynamics, specifically the manual override allowed in dirty air, led to intense DRS trains forming in the midfield.",
      desc2: "Lance Stroll completely bypassed the expected pit window, extending his first stint incredibly deep into the race. The Aston Martin telemetry showed a surprisingly low S1/S3 ratio for him compared to Alonso, meaning his setup was preserving the rear tires much better in the high-speed sections at the cost of straight-line speed.",
      desc3: "Meanwhile, the Red Bulls began flexing their ERS efficiency. Verstappen consistently pulled away from the DRS threat by deploying his MGU-K heavily exiting turn 16, maintaining a 1.2s gap effortlessly while simultaneously charging the battery down the long back straight.",
      contextTitle: "Telemetry Context: Stint Extension",
      contextDesc: "Tire degradation curves on the 2026 compounds are highly non-linear. Stroll managed to keep the carcass temperature in the optimal window, allowing him to bypass the sudden 'cliff' that caught out drivers like Ocon and Magnussen, who lost over 1.5 seconds per lap before pitting.",
      stats: [
        { label: "STR Tire Life", val: "24 Laps" },
        { label: "VER ERS Depletion", val: "Optimal" },
        { label: "Pit Stops", val: "12 Drivers" }
      ],
      logRange: [10, 25]
    },
    {
      id: 2,
      title: "Laps 26 - 35",
      subtitle: "Red Bull Efficiency vs Mercedes Cliff",
      desc: "Following the first cycle of pit stops, the true base pace of the cars revealed itself. Stripped of heavy fuel and traffic, the leading pack engaged in a raw time trial.",
      desc2: "Mercedes suddenly hit a catastrophic aerodynamic cliff. Russell reported severe bouncing in the high-speed sections. The telemetry showed that their active front wing elements were stalling unpredictably, costing them critical downforce. Their sector 1 times plummeted.",
      desc3: "Red Bull and McLaren seized the opportunity. Norris set consecutive fastest laps, utilizing the McLaren's superior low-speed mechanical grip. However, Verstappen responded with metronomic consistency, maintaining a standard deviation in his lap times of just 0.082s—a robotic feat of precision.",
      contextTitle: "Telemetry Context: Active Aero Stall",
      contextDesc: "The 2026 active aero system allows front and rear wings to adjust dynamically. If the hydraulic actuators desynchronize by even a few milliseconds during a high-G corner, the airflow detaches from the floor, causing sudden loss of downforce and subsequent bouncing (porpoising).",
      stats: [
        { label: "VER Consistency", val: "0.082s STD" },
        { label: "NOR Fastest Lap", val: "1:28.4" },
        { label: "RUS Time Loss", val: "-0.8s/lap" }
      ],
      logRange: [25, 35]
    },
    {
      id: 3,
      title: "Laps 36 - 45",
      subtitle: "The Rubbered-In Crossover Point",
      desc: "As the Miami track rubbered in and temperatures slightly cooled, the crossover point for the Hard compound tire arrived. Drivers who gambled on a long Middle Stint began reaping the rewards of massive track evolution.",
      desc2: "Ferrari, who had been quiet all race, suddenly came alive. Leclerc, running a higher downforce setup (S1/S3 ratio heavily favoring Sector 1), found immense grip. He began hunting down the McLarens, utilizing superior traction out of the slow chicanes.",
      desc3: "The midfield battle became chaotic. Alpine and Kick Sauber engaged in a massive scrap, swapping positions multiple times per lap. The telemetry showed extreme spikes in battery deployment, indicating drivers were burning through their ERS allocation desperately to defend.",
      contextTitle: "Telemetry Context: Track Evolution",
      contextDesc: "Track evolution refers to the grip level increasing as cars lay down rubber on the racing line. In Miami, this evolution was worth almost 1.2 seconds of lap time by lap 40. High-downforce setups benefit exponentially from this, as the added mechanical grip multiplies the aerodynamic load.",
      stats: [
        { label: "Track Grip", val: "+1.2s" },
        { label: "LEC Pace Delta", val: "-0.4s/lap" },
        { label: "Overtakes", val: "14" }
      ],
      logRange: [35, 45]
    },
    {
      id: 4,
      title: "Laps 46 - Finish",
      subtitle: "The Gen-Z Active Aero Shootout",
      desc: "The final 10 laps became a sheer sprint to the finish. With fuel loads at their absolute minimum, the cars were operating at peak performance. The 2026 Manual Override (Push-to-Pass) system was heavily utilized.",
      desc2: "Verstappen and Norris engaged in a cat-and-mouse game. Norris saved his Manual Override allocation for the back straight, attempting to break the DRS tow. Verstappen countered by optimizing his corner exits, ensuring he stayed within the critical 1-second delta.",
      desc3: "In the end, it was a test of thermal management vs raw battery power. The telemetry across the grid spiked in the final laps as drivers emptied their energy stores completely, crossing the line in a breathtaking demonstration of the new hybrid era.",
      contextTitle: "Telemetry Context: Manual Override",
      contextDesc: "The 2026 regulations introduced a manual override mode that allows drivers to access the full 350kW electrical deployment for a set duration, bypassing the automated energy management. Misjudging this deployment can leave a driver entirely vulnerable on the next straight.",
      stats: [
        { label: "NOR Override Use", val: "Max" },
        { label: "VER Defenses", val: "Successful" },
        { label: "Final Gap", val: "0.842s" }
      ],
      logRange: [45, 100] // 100 to catch the rest
    }
  ];

  const active = phases.find(p => p.id === activePhase);

  // Safe slicing of logs if available
  const displayLogs = logs && logs.length > 0 
    ? logs.slice(active.logRange[0], active.logRange[1] > logs.length ? logs.length : active.logRange[1])
    : [];

  return (
    <div className="flex flex-col lg:flex-row gap-8 mt-8">
      
      {/* LEFT COLUMN: PHASE SELECTION */}
      <div className="w-full lg:w-1/4 flex flex-col gap-4">
        {phases.map((phase) => {
          const isActive = activePhase === phase.id;
          return (
            <div 
              key={phase.id}
              onClick={() => setActivePhase(phase.id)}
              className={`border rounded-lg p-4 cursor-pointer transition flex items-center justify-between
                ${isActive ? 'bg-zinc-950 border-yellow-600/50' : 'bg-zinc-900 border-zinc-800 hover:bg-zinc-800'}`}
            >
              <div>
                <div className="text-xs font-mono text-zinc-500 mb-1">{phase.title}</div>
                <div className={`font-bold text-sm ${isActive ? 'text-yellow-500' : 'text-zinc-300'}`}>
                  {phase.subtitle}
                </div>
              </div>
              {isActive && <span className="text-yellow-500 font-bold">{'>'}</span>}
            </div>
          );
        })}
      </div>

      {/* RIGHT COLUMN: PHASE DETAILS */}
      <div className="w-full lg:w-3/4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-8 shadow-2xl transition-all duration-300">
          <div className="flex items-center gap-4 mb-6">
            <span className="bg-zinc-800 text-zinc-400 font-mono text-xs px-3 py-1 rounded-full border border-zinc-700">
              Phase {active.id + 1}
            </span>
            <span className="text-yellow-500 font-bold font-mono text-sm">{active.title}</span>
          </div>
          
          <h2 className="text-2xl font-bold text-white mb-6">{active.subtitle}</h2>
          
          <div className="text-zinc-300 space-y-4 mb-8 text-sm leading-relaxed">
            <p>{active.desc}</p>
            <p>{active.desc2}</p>
            <p>{active.desc3}</p>
          </div>

          <div className="bg-zinc-950 border border-blue-900/50 rounded-lg p-6 mb-8 flex gap-4">
            <div className="text-blue-500 text-2xl">ℹ</div>
            <div>
              <h3 className="text-blue-400 font-bold text-sm mb-2 uppercase">{active.contextTitle}</h3>
              <p className="text-zinc-400 text-xs leading-relaxed">
                {active.contextDesc}
              </p>
            </div>
          </div>

          <div>
            <h3 className="text-zinc-500 font-mono text-xs font-bold mb-4 uppercase">Phase Telemetry Context</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {active.stats.map((stat, idx) => (
                <div key={idx} className={`p-4 rounded-lg ${idx === 0 ? 'bg-yellow-950/20 border border-yellow-900/50' : idx === 1 ? 'bg-blue-950/20 border border-blue-900/50' : 'bg-red-950/20 border border-red-900/50'}`}>
                  <div className={`font-mono text-xs mb-1 uppercase ${idx === 0 ? 'text-yellow-600/80' : idx === 1 ? 'text-blue-600/80' : 'text-red-500/80'}`}>
                    {stat.label}
                  </div>
                  <div className={`font-bold text-xl ${idx === 0 ? 'text-yellow-500' : idx === 1 ? 'text-blue-400' : 'text-red-400'}`}>
                    {stat.val}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Fallback to actual logs if needed */}
          {displayLogs.length > 0 && (
            <div className="mt-12 pt-8 border-t border-zinc-800">
               <h3 className="text-zinc-500 font-mono text-xs font-bold mb-4 uppercase">Raw Race Control Logs ({active.title})</h3>
               <div className="h-[200px] overflow-y-auto pr-4">
                 <div className="flex flex-col gap-3 font-mono text-xs">
                  {displayLogs.map((log, idx) => {
                    let bgStyle = "bg-zinc-950 border-zinc-800 text-zinc-300";
                    if (log.Category === "Penalty") bgStyle = "bg-red-950/30 border-red-900 text-red-200";
                    if (log.Category === "SafetyCar") bgStyle = "bg-yellow-950/30 border-yellow-900 text-yellow-200";

                    return (
                      <div key={idx} className={`p-3 rounded border ${bgStyle}`}>
                        <div className="text-zinc-500 mb-1">T+ {log.Time}</div>
                        <div className="font-bold leading-relaxed">{log.Message}</div>
                      </div>
                    );
                  })}
                 </div>
               </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
