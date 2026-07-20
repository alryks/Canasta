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
  highlightedMeldId?: string | null
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
  highlightedMeldId,
  onSelectStealTarget,
}: TeamZoneProps) {
  const fitRef = useRef<HTMLDivElement>(null)
  const stripRef = useRef<HTMLDivElement>(null)
  // Always anchored top: the shell clips/aligns its (possibly taller than
  // itself) strip child from the top too (see .team-zone-shell), so the
  // scaled-down visual content and the clipped/visible slice agree on which
  // edge is "pinned". Anchoring this at the bottom for the own-team zone
  // used to fight that clip, hiding the real content behind blank space
  // once scaling was strong enough for the mismatch to show.
  const { shellStyle, contentStyle } = useFitScale(fitRef, stripRef, [melds], {
    transformOrigin: 'top center',
    minScale: 0.62,
  })

  return (
    <div
      aria-label={`melds-${teamId}`}
      data-team-id={teamId}
      className={`team-zone ${isOwnTeam ? 'team-zone-bottom' : 'team-zone-top'}${
        highlightedTeamId === teamId ? ' is-recent-action' : ''
      }`}
    >
      <h3 className="team-zone-title">
        {isOwnTeam ? 'Ваши комбинации' : 'Комбинации соперников'}
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
                      isRecentAction={highlightedMeldId === meld.id}
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
