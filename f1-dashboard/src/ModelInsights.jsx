import { useState, useEffect } from 'react';

export default function ModelInsights({ year, gp }) {
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeCategory, setActiveCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (!year || !gp) return;

    setLoading(true);
    setError(null);
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    
    fetch(`${apiUrl}/api/insights/${year}/${encodeURIComponent(gp)}`)
      .then(res => {
        if (!res.ok) {
          throw new Error('Failed to load model insights');
        }
        return res.json();
      })
      .then(json => {
        setInsights(json);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load insights:", err);
        setError(err.message);
        setLoading(false);
      });
  }, [year, gp]);

  if (loading) {
    return (
      <div className="h-[40vh] flex flex-col items-center justify-center font-mono text-zinc-400 gap-4">
        <div className="relative flex h-8 w-8">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-8 w-8 bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.8)]"></span>
        </div>
        <span className="text-xs uppercase tracking-widest animate-pulse">Extracting XGBoost Decision Tree Metrics...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-950/20 border border-red-900/50 p-6 rounded-lg font-mono text-red-500 text-xs max-w-lg mx-auto flex flex-col gap-2">
        <h3 className="font-bold text-sm uppercase tracking-wider flex items-center gap-2">
          <span>⚠️</span> Insights Engine Error
        </h3>
        <p className="text-zinc-300">{error}</p>
        <span className="text-[10px] text-zinc-500 border-t border-red-900/20 pt-2 uppercase">
          Ensure model cache is available on backend
        </span>
      </div>
    );
  }

  if (!insights) return null;

  const { calibrated_parameters, feature_importances } = insights;

  // Filter features based on search query and category
  const filteredFeatures = feature_importances.filter(feat => {
    const matchesCategory = activeCategory === 'All' || feat.category === activeCategory;
    const matchesSearch = feat.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          feat.feature.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  // Categories list
  const categories = ['All', 'Practice', 'Qualifying', 'Sprint', 'Power Unit & Aero', 'Recent Form'];

  // Identify top features for GP
  const topFeatures = feature_importances
    .filter(f => f.importance > 0)
    .slice(0, 3)
    .map(f => f.label);

  return (
    <div className="w-full flex flex-col gap-8">
      {/* SECTION HEADER */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-xl font-bold uppercase tracking-wide border-l-4 border-blue-600 pl-3">
            XGBoost Decision Insights
          </h2>
          <p className="text-xs text-zinc-500 font-mono mt-1 uppercase tracking-widest">
            Predictive Model Architecture for {insights.gp}
          </p>
        </div>
      </div>

      {/* DYNAMIC MODEL INTERPRETABILITY LOGIC */}
      <div className="relative bg-zinc-900/40 backdrop-blur-md border border-zinc-800/80 rounded-xl p-6 shadow-xl overflow-hidden">
        <div className="absolute top-0 left-0 w-2 h-full bg-gradient-to-b from-blue-600 to-indigo-600" />
        <h3 className="text-sm font-bold font-mono text-zinc-300 uppercase tracking-widest mb-3">
          Predictive Narrative Summary
        </h3>
        <p className="text-sm text-zinc-400 leading-relaxed font-sans">
          For the <strong className="text-zinc-100">{insights.gp}</strong>, the F1 Oracle XGBRanker model has automatically calibrated its weights. The ranking predictions are heavily driven by performance in <strong className="text-blue-400">{topFeatures[0] || 'Qualifying performance'}</strong>, <strong className="text-blue-400">{topFeatures[1] || 'Practice Longrun Consistency'}</strong>, and <strong className="text-blue-400">{topFeatures[2] || 'Season Pace Form'}</strong>. These inputs represent the critical parameters identified through Leave-One-Out Cross-Validation (LOO-CV) to minimize ranking error on this circuit profile.
        </p>
      </div>

      {/* CALIBRATED PARAMETERS GRID */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Card 1: Upgrade Sensitivity */}
        <div className="bg-zinc-900/60 backdrop-blur-md border border-zinc-800/80 hover:border-zinc-700/80 transition-all rounded-xl p-5 relative overflow-hidden group shadow-lg">
          <div className="absolute top-0 right-0 w-20 h-20 bg-blue-500/5 rounded-bl-full group-hover:bg-blue-500/10 transition-colors" />
          <div className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest">Upgrade Sensitivity (σ)</div>
          <div className="font-orbitron text-4xl font-black text-blue-500 mt-2">
            {calibrated_parameters.upgrade_sigma.toFixed(3)}
          </div>
          <p className="text-xs text-zinc-400 mt-3 font-sans leading-relaxed">
            Determines the time gain shift applied per technical upgrade point. The model applies this shift relative to the variance of the telemetry features.
          </p>
        </div>

        {/* Card 2: Grid Anchor Weight */}
        <div className="bg-zinc-900/60 backdrop-blur-md border border-zinc-800/80 hover:border-zinc-700/80 transition-all rounded-xl p-5 relative overflow-hidden group shadow-lg">
          <div className="absolute top-0 right-0 w-20 h-20 bg-teal-500/5 rounded-bl-full group-hover:bg-teal-500/10 transition-colors" />
          <div className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest">Grid Anchor Coefficient (α)</div>
          <div className="font-orbitron text-4xl font-black text-teal-400 mt-2">
            {calibrated_parameters.grid_anchor_weight.toFixed(3)}
          </div>
          <p className="text-xs text-zinc-400 mt-3 font-sans leading-relaxed">
            The blend ratio of qualifying grid order into the raw model predictions. Higher values are selected for street circuits where track position is dominant.
          </p>
        </div>

        {/* Card 3: Sprint Boost */}
        <div className="bg-zinc-900/60 backdrop-blur-md border border-zinc-800/80 hover:border-zinc-700/80 transition-all rounded-xl p-5 relative overflow-hidden group shadow-lg">
          <div className="absolute top-0 right-0 w-20 h-20 bg-purple-500/5 rounded-bl-full group-hover:bg-purple-500/10 transition-colors" />
          <div className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest">Sprint Finish Coefficient (σs)</div>
          <div className="font-orbitron text-4xl font-black text-purple-400 mt-2">
            {calibrated_parameters.sprint_sigma.toFixed(3)}
          </div>
          <p className="text-xs text-zinc-400 mt-3 font-sans leading-relaxed">
            The weight assigned to sprint finishing results during prediction calculations. Only active on Sprint Weekends.
          </p>
        </div>
      </div>

      {/* FEATURE IMPORTANCE SECTION */}
      <div className="bg-zinc-900/40 backdrop-blur-md border border-zinc-800/80 rounded-xl p-6 shadow-xl flex flex-col gap-6">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 border-b border-zinc-800/60 pb-4">
          <div className="flex flex-col">
            <h3 className="font-orbitron text-sm font-bold text-white uppercase tracking-wider">
              Feature Relevance Rank
            </h3>
            <span className="text-[10px] text-zinc-500 font-mono mt-0.5 uppercase tracking-widest">
              XGBRanker Node Split Weights
            </span>
          </div>
          
          {/* SEARCH BAR */}
          <div className="w-full lg:w-72 relative font-mono text-xs">
            <span className="absolute left-3 top-2.5 text-zinc-500">🔍</span>
            <input
              type="text"
              placeholder="Search features..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-zinc-950/80 border border-zinc-800 hover:border-zinc-700 rounded-lg pl-9 pr-4 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors shadow-inner"
            />
          </div>
        </div>

        {/* CATEGORY TABS */}
        <div className="flex flex-wrap gap-2">
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3 py-1.5 rounded-lg border font-mono text-[10px] font-bold uppercase tracking-wider transition-all ${
                activeCategory === cat
                  ? 'bg-blue-600 border-blue-500 text-white shadow-md'
                  : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-700'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* CHART BODY */}
        <div className="flex flex-col gap-5 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
          {filteredFeatures.length === 0 ? (
            <div className="text-center font-mono text-xs text-zinc-500 py-12 uppercase tracking-widest">
              No matching features in this category
            </div>
          ) : (
            filteredFeatures.map(feat => {
              const pct = (feat.importance * 100);
              
              // Color styling based on feature category
              let barColor = "from-blue-600 to-indigo-600";
              let badgeColor = "bg-blue-950/50 text-blue-400 border-blue-900";
              if (feat.category === "Qualifying") {
                barColor = "from-red-600 to-orange-500";
                badgeColor = "bg-red-950/50 text-red-400 border-red-900";
              } else if (feat.category === "Power Unit & Aero") {
                barColor = "from-emerald-600 to-teal-500";
                badgeColor = "bg-emerald-950/50 text-emerald-400 border-emerald-900";
              } else if (feat.category === "Sprint") {
                barColor = "from-purple-600 to-fuchsia-500";
                badgeColor = "bg-purple-950/50 text-purple-400 border-purple-900";
              } else if (feat.category === "Recent Form") {
                barColor = "from-amber-600 to-yellow-500";
                badgeColor = "bg-amber-950/50 text-amber-400 border-amber-900";
              }

              return (
                <div key={feat.feature} className="flex flex-col gap-1.5 font-mono group">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-sans font-bold text-zinc-300 group-hover:text-white transition-colors">
                      {feat.label}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className={`text-[9px] px-2 py-0.5 rounded border font-semibold uppercase ${badgeColor}`}>
                        {feat.category}
                      </span>
                      <span className="font-bold text-zinc-100 min-w-[50px] text-right">
                        {pct.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                  
                  {/* BAR PROGRESS */}
                  <div className="w-full bg-zinc-950 rounded-full h-3 border border-zinc-800/80 p-0.5 shadow-inner">
                    <div
                      className={`bg-gradient-to-r ${barColor} h-1.5 rounded-full transition-all duration-700 ease-out group-hover:brightness-110 shadow-[0_0_8px_rgba(59,130,246,0.2)]`}
                      style={{ width: `${Math.max(1.5, pct)}%` }}
                    />
                  </div>
                  
                  {/* METADATA SUBTITLE ON HOVER */}
                  <span className="text-[9px] text-zinc-600 uppercase tracking-widest hidden group-hover:inline-block transition-all mt-0.5 animate-fadeIn">
                    Raw Metric: {feat.feature}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
