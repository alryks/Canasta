import type { Meld } from '../lib/protocol'
import { MeldStack } from './MeldStack'

interface StealTarget {
  meldId: string
  wildCardId: string
}

interface TeamZoneProps {
  teamId: string
  melds: Meld[]
  isOwnTeam: boolean
  canAddCards: boolean
  onAddToMeld: (meldId: string) => void
  canDragAdd?: boolean
  canStealFrom: boolean
  stealTarget: StealTarget | null
  onSelectStealTarget: (meldId: string, cardId: string) => void
}

export function TeamZone({
  teamId,
  melds,
  isOwnTeam,
  canAddCards,
  onAddToMeld,
  canDragAdd,
  canStealFrom,
  stealTarget,
  onSelectStealTarget,
}: TeamZoneProps) {
  return (
    <div
      aria-label={`melds-${teamId}`}
      className={`team-zone ${isOwnTeam ? 'team-zone-bottom' : 'team-zone-top'}`}
    >
      <h3 className="team-zone-title">Команда {teamId}</h3>
      <ul className="meld-row">
        {melds.map((meld) => (
          <li key={meld.id}>
            <MeldStack
              meld={meld}
              isOwnTeam={isOwnTeam}
              canAddCards={canAddCards}
              onAddToMeld={() => onAddToMeld(meld.id)}
              canDragAdd={canDragAdd}
              canStealFrom={canStealFrom}
              isStealTarget={(cardId) =>
                stealTarget?.meldId === meld.id && stealTarget.wildCardId === cardId
              }
              onSelectStealTarget={(cardId) => onSelectStealTarget(meld.id, cardId)}
            />
          </li>
        ))}
      </ul>
    </div>
  )
}
