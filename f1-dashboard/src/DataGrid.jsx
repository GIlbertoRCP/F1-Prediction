export default function DataGrid({ data }) {
  if (!data || !data.predictions || !data.actuals) return null;

  return (
    <div className="w-full">
      <h2 className="text-xl font-bold mb-4 uppercase tracking-wide border-l-4 border-red-600 pl-3">
        Prediction vs Reality
      </h2>
      <div className="bg-zinc-900 rounded-lg border border-zinc-800 overflow-hidden shadow-2xl">
        <table className="w-full text-left font-mono text-sm">
          <thead className="bg-zinc-950 text-zinc-400 border-b border-zinc-800">
            <tr>
              <th className="p-4 w-16 text-center">PRD</th>
              <th className="p-4 w-16 text-center">ACT</th>
              <th className="p-4">DRIVER</th>
              <th className="p-4 hidden sm:table-cell">TEAM</th>
              <th className="p-4 text-right">DELTA</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {data.predictions.map((pred) => {
              const actual = data.actuals.find(a => a.Driver === pred.Driver);
              const actPos = actual ? actual.actual_position : '-';
              
              const delta = actual ? pred.predicted_position - actual.actual_position : null;
              let deltaColor = "text-zinc-500";
              let deltaText = "-";
              if (delta > 0) { deltaColor = "text-green-500"; deltaText = `▲ +${delta}`; }
              if (delta < 0) { deltaColor = "text-red-500"; deltaText = `▼ ${delta}`; }

              let teamBorder = "border-zinc-700";
              if (pred.Team === "Red Bull Racing") teamBorder = "border-blue-700";
              if (pred.Team === "McLaren") teamBorder = "border-orange-500";
              if (pred.Team === "Ferrari") teamBorder = "border-red-600";
              if (pred.Team === "Mercedes") teamBorder = "border-teal-400";
              if (pred.Team === "Aston Martin") teamBorder = "border-green-600";

              return (
                <tr key={pred.Driver} className="hover:bg-zinc-800/50 transition-colors">
                  <td className="p-4 text-center font-bold text-zinc-500">P{pred.predicted_position}</td>
                  <td className="p-4 text-center font-bold text-white">P{actPos}</td>
                  <td className={`p-4 font-bold border-l-4 ${teamBorder}`}>{pred.Driver}</td>
                  <td className="p-4 text-zinc-400 hidden sm:table-cell">{pred.Team}</td>
                  <td className={`p-4 text-right font-bold ${deltaColor}`}>{deltaText}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
