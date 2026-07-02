interface LobbySettingsPanelProps {
  targetScore: number
  discardVisibility: string
  isHost: boolean
  onChange: (settings: { target_score?: number; discard_visibility?: string }) => void
}

export function LobbySettingsPanel({
  targetScore,
  discardVisibility,
  isHost,
  onChange,
}: LobbySettingsPanelProps) {
  if (!isHost) {
    return (
      <p className="status-line">
        Цель: {targetScore} очков. Видимость сброса:{' '}
        {discardVisibility === 'FULL' ? 'вся стопка' : 'только верхняя карта'}.
      </p>
    )
  }

  return (
    <div>
      <div className="field">
        <label htmlFor="target-score">Целевой счёт</label>
        <input
          id="target-score"
          className="input"
          type="number"
          min={1000}
          step={500}
          value={targetScore}
          onChange={(event) => onChange({ target_score: Number(event.target.value) })}
        />
      </div>

      <div className="field">
        <label htmlFor="discard-visibility">Видимость сброса</label>
        <select
          id="discard-visibility"
          className="input"
          value={discardVisibility}
          onChange={(event) => onChange({ discard_visibility: event.target.value })}
        >
          <option value="TOP_ONLY">Только верхняя карта</option>
          <option value="FULL">Вся стопка</option>
        </select>
      </div>
    </div>
  )
}
