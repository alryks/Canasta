import { useRef } from 'react'
import { useFitScale } from '../lib/useFitScale'
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
  canDragAdd?: boolean
  canStealFrom: boolean
  stealTarget: StealTarget | null
  highlightedTeamId?: string | null
  highlightedCardIds?: string[]
  onSelectStealTarget: (meldId: string, cardId: string) => void
}

export function TeamZone({
  teamId,
  melds,
  isOwnTeam,
  canDragAdd,
  canStealFrom,
  stealTarget,
  highlightedTeamId,
  highlightedCardIds = [],
  onSelectStealTarget,
}: TeamZoneProps) {
  const fitRef = useRef<HTMLDivElement>(null)
  const stripRef = useRef<HTMLDivElement>(null)
  const { shellStyle, contentStyle } = useFitScale(
    fitRef,
    stripRef,
    [melds],
    { transformOrigin: isOwnTeam ? 'bottom center' : 'top center' },
  )

  return (
    <div
      aria-label={`melds-${teamId}`}
      className={`team-zone ${isOwnTeam ? 'team-zone-bottom' : 'team-zone-top'}${
        highlightedTeamId === teamId ? ' is-recent-action' : ''
      }`}
    >
      <h3 className="team-zone-title">
        {isOwnTeam ? 'Ваши комбинации' : `Соперники · команда ${teamId}`}
      </h3>
      <div className="team-zone-fit" ref={fitRef}>
        {melds.length > 0 && (
          <div className="team-zone-shell" style={shellStyle}>
            <div className="team-zone-strip" ref={stripRef} style={contentStyle}>
              <ul className="meld-row">
                {melds.map((meld) => (
                  <li key={meld.id}>
                    <MeldStack
                      meld={meld}
                      isOwnTeam={isOwnTeam}
                      canDragAdd={canDragAdd}
                      canStealFrom={canStealFrom}
                      highlightedCardIds={highlightedCardIds}
                      isStealTarget={(cardId) =>
                        stealTarget?.meldId === meld.id && stealTarget.wildCardId === cardId
                      }
                      onSelectStealTarget={(cardId) => onSelectStealTarget(meld.id, cardId)}
                    />
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
