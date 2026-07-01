interface ThresholdIndicatorProps {
  teamId: string
  accumulated: number
  threshold: number
}

// FR: progress toward the opening threshold, hidden once the team is
// opened. The server doesn't send is_opened explicitly (ws/serialization.py
// only sends turn_accumulator/thresholds), but engine.py's
// _maybe_open_team never resets turn_accumulator once it clears the
// threshold, so the comparison is a safe standing proxy for is_opened.
export function ThresholdIndicator({
  teamId,
  accumulated,
  threshold,
}: ThresholdIndicatorProps) {
  if (accumulated >= threshold) return null

  return (
    <p aria-label={`threshold-${teamId}`}>
      Порог открытия команды {teamId}: {accumulated}/{threshold}
    </p>
  )
}
