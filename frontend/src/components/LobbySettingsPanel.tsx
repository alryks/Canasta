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
  const setDiscardVisibility = (value: string) => {
    if (value !== discardVisibility) onChange({ discard_visibility: value })
  }

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
        <span className="field-label">Видимость сброса</span>
        <div
          className="setting-toggle"
          role="radiogroup"
          aria-label="Видимость сброса"
        >
          <button
            type="button"
            className={`setting-toggle-option${discardVisibility === 'TOP_ONLY' ? ' is-active' : ''}`}
            aria-pressed={discardVisibility === 'TOP_ONLY'}
            onClick={() => setDiscardVisibility('TOP_ONLY')}
          >
            Верхняя карта
          </button>
          <button
            type="button"
            className={`setting-toggle-option${discardVisibility === 'FULL' ? ' is-active' : ''}`}
            aria-pressed={discardVisibility === 'FULL'}
            onClick={() => setDiscardVisibility('FULL')}
          >
            Вся стопка
          </button>
        </div>
      </div>
    </div>
  )
}
