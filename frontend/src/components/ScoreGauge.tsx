import { getScoreColor, getVerdictLabel } from "../lib/formatting";

interface ScoreGaugeProps {
  score: number;
  size?: number;
  label?: string;
}

export default function ScoreGauge({ score, size = 180, label }: ScoreGaugeProps) {
  const strokeWidth = size * 0.08;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;
  const color = getScoreColor(score);

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <div
        className="absolute flex flex-col items-center justify-center"
        style={{ width: size, height: size }}
      >
        <span className="font-bold" style={{ fontSize: size * 0.28, color }}>
          {score}
        </span>
        <span className="text-gray-400" style={{ fontSize: size * 0.09 }}>
          / 100
        </span>
      </div>
      {label && <p className="mt-2 text-sm font-medium text-gray-600">{label}</p>}
      <p className="text-sm font-medium" style={{ color }}>
        {getVerdictLabel(score)}
      </p>
    </div>
  );
}
