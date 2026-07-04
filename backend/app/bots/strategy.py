"""Bot decision-making (plan follow-up: fill empty lobby seats with bots so a
game can be tested/played without needing 4 humans).

`BotStrategy` is the one seam a smarter bot plugs into later -- a strategy
only has to answer "what's my next WS intent", it never touches the engine,
Redis, or broadcasting directly. `app/ws/bot_runner.py` drives it against the
exact same `apply_game_intent` pipeline real WS messages go through, so a
bot is indistinguishable from a slow human from the engine's point of view.
"""

from __future__ import annotations

import random
from typing import Protocol

from app.engine.actions import DrawDeck, DrawDiscard
from app.engine.engine import DealState, apply_action, final_deal_scores
from app.engine.errors import IllegalActionError
from app.engine.models import (
    CANASTA_SIZE,
    MELDABLE_RANKS,
    Card,
    Meld,
    MeldKind,
    Rank,
    Suit,
    TeamTable,
)
from app.engine.scoring import ExitType
from app.engine.turn_fsm import TurnPhase


class BotStrategy(Protocol):
    def choose_intent(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        """Return the next (intent, data) to send on this bot's turn -- called
        again after every resulting game_state, same as a real client reacting
        to each snapshot, until the turn passes to someone else."""
        ...


class SimpleBotStrategy:
    """Draws from the deck and discards the first card in hand; the engine
    auto-applies the -1000 penalty when a discard violates pickup/threshold
    rules. Never takes the discard pile and never melds.
    """

    def choose_intent(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        turn = deal.turn_state

        if turn.phase == TurnPhase.DRAW:
            return "draw_deck", {}

        if turn.phase == TurnPhase.ACT:
            hand = deal.hands[player_id]
            return "discard", {"card_id": hand[0].id}

        raise RuntimeError(f"SimpleBotStrategy has no move for phase {turn.phase!r}")


def _naturals_by_rank(cards: list[Card]) -> dict[Rank, list[Card]]:
    groups: dict[Rank, list[Card]] = {}
    for card in cards:
        if not card.is_wild and not card.is_three:
            groups.setdefault(card.rank, []).append(card)
    return groups


def _wilds_of(cards: list[Card]) -> list[Card]:
    # ascending point value: spend twos before jokers
    return sorted((c for c in cards if c.is_wild), key=lambda c: c.point_value)


def _set_value(cards: list[Card]) -> int:
    value = sum(c.point_value for c in cards)
    if len(cards) >= CANASTA_SIZE:
        value += 500 if all(not c.is_wild for c in cards) else 200
    return value


def _sequence_extension_ranks(meld: Meld) -> tuple[Suit, list[Rank]]:
    """The (suit, exact ranks) that would extend this SEQUENCE meld by one."""
    suit_value, start_rank_value = meld.rank_or_suit_anchor.split(":")
    suit = Suit(suit_value)
    start = MELDABLE_RANKS.index(Rank(start_rank_value))
    end = start + meld.size - 1
    ranks: list[Rank] = []
    if start > 0:
        ranks.append(MELDABLE_RANKS[start - 1])
    if end < len(MELDABLE_RANKS) - 1:
        ranks.append(MELDABLE_RANKS[end + 1])
    return suit, ranks


class HeuristicBotStrategy:
    """Plays like a reasonable club player, using only information a human in
    the seat would have (own hand, both tables, top of the discard pile and
    card counts -- never other hands or the deck order):

    - opens only when it can cover the whole threshold within one turn;
    - takes the discard pile when the top card completes a real new meld
      (mandatory-meld and threshold obligations checked before committing);
    - builds natural sets, extends the team's sets and sequences, and spends
      wilds mostly as the finishing card of a canasta;
    - steals opponents' wilds when it holds a spare replacement natural;
    - discards black threes first, junk singletons next, and never lets go of
      wilds or red threes while it has any other choice;
    - never melds itself into an empty hand unless that ends the deal.
    """

    # keep at least this many non-three cards after an optional meld so the
    # bot doesn't strip its own hand bare before the team can go out
    HAND_FLOOR = 2

    def choose_intent(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        turn = deal.turn_state
        if turn.phase == TurnPhase.DRAW:
            return self._choose_draw(deal, player_id)
        if turn.phase == TurnPhase.ACT:
            return self._choose_act(deal, player_id)
        raise RuntimeError(f"HeuristicBotStrategy has no move for phase {turn.phase!r}")

    # --- DRAW phase ---

    def _choose_draw(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        if self._should_take_discard_pile(deal, player_id):
            return "draw_discard", {}
        return "draw_deck", {}

    def _should_take_discard_pile(self, deal: DealState, player_id: str) -> bool:
        pile = deal.discard_pile
        if not pile:
            return False
        top = pile[-1]
        if top.is_three:
            return False  # blocked by the rules

        team = deal.team_of(player_id)
        hand = deal.hands[player_id]
        groups = _naturals_by_rank(hand)
        wilds = _wilds_of(hand)

        if top.is_wild:
            # a free wild is worth it only if the mandatory fresh meld can
            # still come straight from hand
            return team.is_opened and self._best_new_set(groups, [], allow_wild=False) is not None

        same_rank = groups.get(top.rank, [])
        if team.is_opened:
            # the mandatory new meld takes 3 cards; if that would empty the
            # post-pickup hand without a canasta the turn wedges -- skip
            if len(hand) + len(pile) <= 3 and not any(
                m.is_closed for m in team.melds
            ):
                return False
            if len(same_rank) >= 2:
                return True
            # spending a wild to unlock the pile only pays off for a real pile
            return len(same_rank) == 1 and bool(wilds) and len(pile) >= 3

        # unopened: everything laid this turn must cover the threshold, and
        # the top card itself must anchor one of the new melds
        if len(same_rank) < 2:
            return False
        team_id = deal.player_team[player_id]
        needed = deal.thresholds[team_id] - team.turn_accumulator
        plan = self._opening_plan([*hand, top], needed, team)
        if plan is None:
            return False
        return any(top.id in {c.id for c in meld_cards} for meld_cards in plan)

    # --- ACT phase ---

    def _choose_act(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        turn = deal.turn_state
        team = deal.team_of(player_id)
        hand = deal.hands[player_id]
        must_create = (
            turn.must_meld_after_pickup and turn.melds_created_this_turn == 0
        )

        if team.is_opened:
            action = self._opened_meld_action(deal, player_id, must_create)
            if action is not None:
                return action
        else:
            team_id = deal.player_team[player_id]
            needed = deal.thresholds[team_id] - team.turn_accumulator
            plan = self._opening_plan(hand, needed, team)
            if plan:
                return "create_meld", {"card_ids": [c.id for c in plan[0]]}

        if must_create and not turn.pending_penalty:
            # nothing legal to lay after taking the pile -- own up to the
            # -1000 so the discard becomes legal instead of stalling the turn
            return "concede_penalty", {}
        return self._choose_discard(deal, player_id)

    def _opened_meld_action(
        self, deal: DealState, player_id: str, must_create: bool
    ) -> tuple[str, dict] | None:
        hand = deal.hands[player_id]
        team = deal.team_of(player_id)
        groups = _naturals_by_rank(hand)
        wilds = _wilds_of(hand)
        open_melds = [m for m in team.melds if not m.is_closed]

        if must_create:
            cards = self._best_new_set(groups, wilds, allow_wild=True)
            if cards is None and len(wilds) >= 3:
                cards = wilds[:CANASTA_SIZE]  # wild canasta as a last resort
            if cards is not None and self._may_spend(
                deal,
                player_id,
                {c.id for c in cards},
                closes_canasta=len(cards) >= CANASTA_SIZE,
                mandatory=True,
            ):
                return "create_meld", {"card_ids": [c.id for c in cards]}
            return None

        # 1. finish a canasta (biggest single swing on the table)
        for meld in open_melds:
            take = self._closing_add(meld, groups, wilds)
            if take is not None and self._may_spend(
                deal, player_id, {c.id for c in take}, closes_canasta=True
            ):
                return "add_to_meld", {
                    "meld_id": meld.id,
                    "card_ids": [c.id for c in take],
                }

        # 2. steal an opponent wild we can immediately hold/use
        steal = self._find_steal(deal, player_id, groups)
        if steal is not None:
            return steal

        # 3. grow the team's melds with matching naturals
        for meld in open_melds:
            take = self._growing_add(meld, groups)
            if take and self._may_spend(
                deal,
                player_id,
                {c.id for c in take},
                closes_canasta=meld.size + len(take) >= CANASTA_SIZE,
            ):
                return "add_to_meld", {
                    "meld_id": meld.id,
                    "card_ids": [c.id for c in take],
                }

        # 4. lay a fresh natural set
        cards = self._best_new_set(groups, [], allow_wild=False)
        if cards is not None and self._may_spend(
            deal, player_id, {c.id for c in cards}, closes_canasta=len(cards) >= CANASTA_SIZE
        ):
            return "create_meld", {"card_ids": [c.id for c in cards]}

        # 5. drowning in wilds: start a wild canasta (worth 1000 completed)
        if len(wilds) >= 4 and not any(
            m.kind == MeldKind.WILD_CANASTA for m in team.melds
        ):
            cards = wilds[:CANASTA_SIZE]
            if self._may_spend(
                deal, player_id, {c.id for c in cards}, closes_canasta=len(cards) >= CANASTA_SIZE
            ):
                return "create_meld", {"card_ids": [c.id for c in cards]}

        return None

    def _closing_add(
        self, meld: Meld, groups: dict[Rank, list[Card]], wilds: list[Card]
    ) -> list[Card] | None:
        """Cards from hand that bring `meld` to exactly 7, or None."""
        space = CANASTA_SIZE - meld.size

        if meld.kind == MeldKind.WILD_CANASTA:
            if len(wilds) >= space:
                return wilds[:space]
            return None

        if meld.kind == MeldKind.SET:
            fits = groups.get(Rank(meld.rank_or_suit_anchor), [])
            if len(fits) >= space:
                return fits[:space]
            # naturals + one wild as the finishing card
            if wilds and len(fits) == space - 1:
                take = [*fits, wilds[-1]]
                new_wild = meld.wild_count + 1
                new_natural = meld.natural_count + len(fits)
                if new_wild <= new_natural:
                    return take
            return None

        if meld.kind == MeldKind.SEQUENCE and space == 1:
            suit, ranks = _sequence_extension_ranks(meld)
            for rank in ranks:
                for card in groups.get(rank, []):
                    if card.suit == suit:
                        return [card]
        return None

    def _growing_add(
        self, meld: Meld, groups: dict[Rank, list[Card]]
    ) -> list[Card] | None:
        """Naturals from hand that extend `meld` without necessarily closing it."""
        space = CANASTA_SIZE - meld.size
        if space <= 0:
            return None
        if meld.kind == MeldKind.SET:
            fits = groups.get(Rank(meld.rank_or_suit_anchor), [])
            return fits[:space] or None
        if meld.kind == MeldKind.SEQUENCE:
            suit, ranks = _sequence_extension_ranks(meld)
            for rank in ranks:
                for card in groups.get(rank, []):
                    if card.suit == suit:
                        return [card]
        return None

    def _best_new_set(
        self,
        groups: dict[Rank, list[Card]],
        wilds: list[Card],
        *,
        allow_wild: bool,
    ) -> list[Card] | None:
        """The most valuable set creatable right now (3+ naturals, or, when
        `allow_wild`, 2 naturals + a two/joker)."""
        best: list[Card] | None = None
        for cards in groups.values():
            candidate: list[Card] | None = None
            if len(cards) >= 3:
                candidate = cards[:CANASTA_SIZE]
            elif allow_wild and len(cards) == 2 and wilds:
                candidate = [*cards, wilds[0]]
            if candidate and (best is None or _set_value(candidate) > _set_value(best)):
                best = candidate
        return best

    def _find_steal(
        self, deal: DealState, player_id: str, groups: dict[Rank, list[Card]]
    ) -> tuple[str, dict] | None:
        """Steal an opponent's wild when we hold a spare natural for its slot:
        exactly one copy in hand and no use for it in our own melds."""
        own_team_id = deal.player_team[player_id]
        for team_id, table in deal.teams.items():
            if team_id == own_team_id:
                continue
            for meld in table.melds:
                if meld.kind == MeldKind.WILD_CANASTA:
                    continue
                for pos, card in enumerate(meld.slots):
                    if card is None or not card.is_wild:
                        continue
                    replacement = self._spare_replacement(deal, own_team_id, meld, pos, groups)
                    if replacement is not None:
                        return "steal_wild", {
                            "meld_id": meld.id,
                            "wild_card_id": card.id,
                            "replacement_card_id": replacement.id,
                        }
        return None

    def _spare_replacement(
        self,
        deal: DealState,
        own_team_id: str,
        meld: Meld,
        pos: int,
        groups: dict[Rank, list[Card]],
    ) -> Card | None:
        if meld.kind == MeldKind.SET:
            candidates = groups.get(Rank(meld.rank_or_suit_anchor), [])
        else:  # SEQUENCE: the exact suit+rank of that slot
            suit_value, start_rank_value = meld.rank_or_suit_anchor.split(":")
            required = MELDABLE_RANKS[
                MELDABLE_RANKS.index(Rank(start_rank_value)) + pos
            ]
            candidates = [
                c
                for c in groups.get(required, [])
                if c.suit == Suit(suit_value)
            ]
        if len(candidates) != 1:
            return None  # pairs and better stay in hand for our own sets
        card = candidates[0]
        if self._fits_team_meld(deal, own_team_id, card):
            return None
        return card

    def _fits_team_meld(self, deal: DealState, team_id: str, card: Card) -> bool:
        for meld in deal.teams[team_id].melds:
            if meld.is_closed:
                continue
            if meld.kind == MeldKind.SET and card.rank.value == meld.rank_or_suit_anchor:
                return True
            if meld.kind == MeldKind.SEQUENCE:
                suit, ranks = _sequence_extension_ranks(meld)
                if card.suit == suit and card.rank in ranks:
                    return True
        return False

    # --- opening ---

    def _opening_plan(
        self, cards: list[Card], needed: int, team: TeamTable
    ) -> list[list[Card]] | None:
        """A list of create_meld card groups whose combined opening value
        reaches `needed`, or None. Natural sets first, then a wild completes
        a pair, then leftover wilds (jokers first) pad the laid sets."""
        groups = _naturals_by_rank(cards)
        wilds = _wilds_of(cards)

        melds: list[list[Card]] = []
        pairs: list[list[Card]] = []
        for cs in sorted(
            groups.values(), key=lambda cs: -_set_value(cs[:CANASTA_SIZE])
        ):
            if len(cs) >= 3:
                melds.append(cs[:CANASTA_SIZE])
            elif len(cs) == 2:
                pairs.append(cs)

        def total() -> int:
            return sum(_set_value(m) for m in melds)

        if total() < max(needed, 1):
            # complete the most valuable pairs with cheap wilds
            for pair in sorted(pairs, key=lambda cs: -cs[0].point_value):
                if not wilds or total() >= needed:
                    break
                melds.append([*pair, wilds.pop(0)])

        # still short: pad existing sets with the remaining wilds, jokers first
        while total() < needed and wilds and melds:
            wild = wilds.pop()
            target = next(
                (
                    m
                    for m in melds
                    if len(m) < CANASTA_SIZE
                    and sum(1 for c in m if c.is_wild) + 1
                    <= sum(1 for c in m if not c.is_wild)
                ),
                None,
            )
            if target is None:
                break
            target.append(wild)

        if not melds or total() < needed:
            return None

        # never plan ourselves into an empty hand unless the plan itself
        # finishes a canasta (the auto clean exit would then end the deal)
        used = {c.id for m in melds for c in m}
        leftover = [c for c in cards if c.id not in used]
        plan_closes = any(len(m) >= CANASTA_SIZE for m in melds)
        team_has_canasta = any(m.is_closed for m in team.melds)
        if not leftover and not plan_closes and not team_has_canasta:
            trimmed = melds[:-1]
            if not trimmed or sum(_set_value(m) for m in trimmed) < needed:
                return None
            melds = trimmed

        return melds

    # --- hand-preservation guard ---

    def _may_spend(
        self,
        deal: DealState,
        player_id: str,
        used_ids: set[str],
        *,
        closes_canasta: bool,
        mandatory: bool = False,
    ) -> bool:
        hand = deal.hands[player_id]
        team = deal.team_of(player_id)
        rest = [c for c in hand if c.id not in used_ids]
        team_has_canasta = closes_canasta or any(m.is_closed for m in team.melds)

        if not rest:
            # a truly empty hand wedges the turn unless the auto clean exit
            # (which needs a closed canasta) ends the deal right here
            return team_has_canasta
        if all(c.is_three for c in rest):
            # with a canasta this is the going-out move; without one a three
            # can still be discarded, so the turn never wedges
            return True

        if mandatory or closes_canasta or team_has_canasta:
            return True
        rest_playable = sum(1 for c in rest if not c.is_three)
        return rest_playable >= self.HAND_FLOOR

    # --- discard ---

    def _choose_discard(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        hand = deal.hands[player_id]
        team_id = deal.player_team[player_id]

        black = next((c for c in hand if c.is_black_three), None)
        if black is not None:
            return "discard", {"card_id": black.id}

        candidates = [c for c in hand if not c.is_wild and not c.is_three]
        if not candidates:
            candidates = [c for c in hand if not c.is_red_three] or list(hand)

        groups = _naturals_by_rank(hand)

        def keep_score(card: Card) -> tuple[int, int, int]:
            if card.is_wild or card.is_three:
                return (100, 100, 0)
            copies = len(groups.get(card.rank, []))
            fits = 1 if self._fits_team_meld(deal, team_id, card) else 0
            # prefer letting go of the highest-value junk to cut hand liability
            return (fits, copies, -card.point_value)

        victim = min(candidates, key=keep_score)
        return "discard", {"card_id": victim.id}


class AdvancedBotStrategy:
    """Tournament-level Canasta bot.

    Key upgrades over HeuristicBotStrategy:
    1. Aggressive pile taking — values full pile size, not just top-card match.
    2. Opponent-danger discard scoring — never feeds an open enemy meld.
    3. Canasta-race awareness — uses wilds more freely when opponents are one
       card away from closing a canasta.
    4. Wild conservation — prefers spending twos before jokers for new sets;
       saves jokers for the canasta-closing play.
    5. Meld prioritisation by proximity — closes the biggest (nearest to 7)
       meld first, not just any open meld.
    6. Avoids duplicate-rank new melds — won't start a second open meld for
       the same rank it already has on the table.
    """

    HAND_FLOOR = 2

    def choose_intent(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        turn = deal.turn_state
        if turn.phase == TurnPhase.DRAW:
            return self._choose_draw(deal, player_id)
        if turn.phase == TurnPhase.ACT:
            return self._choose_act(deal, player_id)
        raise RuntimeError(f"AdvancedBotStrategy: no move for phase {turn.phase!r}")

    # ── DRAW ──────────────────────────────────────────────────────────────────

    def _choose_draw(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        if self._should_take_pile(deal, player_id):
            return "draw_discard", {}
        return "draw_deck", {}

    def _should_take_pile(self, deal: DealState, player_id: str) -> bool:
        pile = deal.discard_pile
        if not pile:
            return False
        top = pile[-1]
        if top.is_three:
            return False

        team_id = deal.player_team[player_id]
        team = deal.teams[team_id]
        hand = deal.hands[player_id]
        groups = _naturals_by_rank(hand)
        wilds = _wilds_of(hand)

        if top.is_wild:
            # Free wild on top: take only if we can meld from hand without it.
            can_meld_without = (
                self._best_new_set(groups, [], allow_wild=False) is not None
            )
            return team.is_opened and can_meld_without

        top_count = len(groups.get(top.rank, []))
        pile_size = len(pile)

        if team.is_opened:
            if top_count >= 2:
                return True  # strong: immediate set
            if top_count == 1 and wilds and pile_size >= 3:
                return True  # one natural + wild completion on a decent pile
            if pile_size >= 5:
                # Large pile: worth taking if combined cards produce any 3-of-kind
                combined_groups = _naturals_by_rank([*hand, *pile])
                if any(len(g) >= 3 for g in combined_groups.values()):
                    return True
                # Or if pile contains 2+ wilds and top matches at least 1
                pile_wilds = sum(1 for c in pile if c.is_wild)
                if pile_wilds >= 2 and top_count >= 1:
                    return True
            return False

        # Unopened: must be able to cover the opening threshold with pile cards.
        if top_count < 2:
            return False
        needed = deal.thresholds[team_id] - team.turn_accumulator
        plan = self._opening_plan([*hand, top], needed, team)
        if plan is None:
            return False
        return any(top.id in {c.id for c in meld_cards} for meld_cards in plan)

    # ── ACT ───────────────────────────────────────────────────────────────────

    def _choose_act(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        turn = deal.turn_state
        team_id = deal.player_team[player_id]
        team = deal.teams[team_id]
        hand = deal.hands[player_id]
        must_create = turn.must_meld_after_pickup and turn.melds_created_this_turn == 0

        if team.is_opened:
            action = self._opened_act(deal, player_id, must_create)
            if action is not None:
                return action
        else:
            needed = deal.thresholds[team_id] - team.turn_accumulator
            plan = self._opening_plan(hand, needed, team)
            if plan:
                return "create_meld", {"card_ids": [c.id for c in plan[0]]}

        if must_create and not turn.pending_penalty:
            return "concede_penalty", {}

        return self._choose_discard(deal, player_id)

    def _opened_act(
        self, deal: DealState, player_id: str, must_create: bool
    ) -> tuple[str, dict] | None:
        hand = deal.hands[player_id]
        team_id = deal.player_team[player_id]
        team = deal.teams[team_id]
        groups = _naturals_by_rank(hand)
        wilds = _wilds_of(hand)
        open_melds = [m for m in team.melds if not m.is_closed]

        # Detect canasta race: opponent has a meld with 6 cards (one away).
        racing = self._opponent_near_canasta(deal, team_id)

        if must_create:
            cards = self._best_new_set(groups, wilds, allow_wild=True)
            if cards is None and len(wilds) >= 3:
                cards = wilds[:CANASTA_SIZE]
            if cards and self._may_spend(
                deal, player_id, {c.id for c in cards},
                closes_canasta=len(cards) >= CANASTA_SIZE, mandatory=True,
            ):
                return "create_meld", {"card_ids": [c.id for c in cards]}
            return None

        # 1. Close the meld nearest to canasta first.
        for meld in sorted(open_melds, key=lambda m: -m.size):
            take = self._closing_cards(meld, groups, wilds, racing=racing)
            if take and self._may_spend(
                deal, player_id, {c.id for c in take}, closes_canasta=True
            ):
                return "add_to_meld", {
                    "meld_id": meld.id,
                    "card_ids": [c.id for c in take],
                }

        # 2. Steal an opponent wild we can immediately replace.
        steal = self._find_steal(deal, player_id, groups)
        if steal:
            return steal

        # 3. Grow existing melds (naturals only, sorted biggest first).
        for meld in sorted(open_melds, key=lambda m: -m.size):
            take = self._growing_cards(meld, groups)
            if take and self._may_spend(
                deal, player_id, {c.id for c in take},
                closes_canasta=meld.size + len(take) >= CANASTA_SIZE,
            ):
                return "add_to_meld", {
                    "meld_id": meld.id,
                    "card_ids": [c.id for c in take],
                }

        # 4. Start a new meld (set or sequence depending on subclass).
        new_meld = self._pick_new_meld(groups, wilds, deal, player_id)
        if new_meld and self._may_spend(
            deal, player_id, {c.id for c in new_meld},
            closes_canasta=len(new_meld) >= CANASTA_SIZE,
        ):
            return "create_meld", {"card_ids": [c.id for c in new_meld]}

        # 5. Wild canasta if drowning in wilds.
        if len(wilds) >= 4 and not any(
            m.kind == MeldKind.WILD_CANASTA for m in team.melds
        ):
            cards = wilds[:CANASTA_SIZE]
            if self._may_spend(
                deal, player_id, {c.id for c in cards},
                closes_canasta=len(cards) >= CANASTA_SIZE,
            ):
                return "create_meld", {"card_ids": [c.id for c in cards]}

        return None

    # ── MELD HELPERS ──────────────────────────────────────────────────────────

    def _closing_cards(
        self,
        meld: Meld,
        groups: dict[Rank, list[Card]],
        wilds: list[Card],
        *,
        racing: bool = False,
    ) -> list[Card] | None:
        """Cards from hand that bring `meld` to exactly 7."""
        space = CANASTA_SIZE - meld.size

        if meld.kind == MeldKind.WILD_CANASTA:
            return wilds[:space] if len(wilds) >= space else None

        if meld.kind == MeldKind.SET:
            rank = Rank(meld.rank_or_suit_anchor)
            fits = groups.get(rank, [])
            if len(fits) >= space:
                return fits[:space]
            if wilds and len(fits) == space - 1:
                # Prefer cheap twos; use jokers freely when racing.
                cheap = [w for w in wilds if w.rank != Rank.JOKER]
                use_wild = wilds[0] if racing else (cheap[0] if cheap else wilds[-1])
                take = [*fits, use_wild]
                new_wild = meld.wild_count + 1
                new_nat = meld.natural_count + len(fits)
                if new_wild <= new_nat:
                    return take
            return None

        if meld.kind == MeldKind.SEQUENCE and space == 1:
            suit_val, start_rank_val = meld.rank_or_suit_anchor.split(":")
            suit = Suit(suit_val)
            start = MELDABLE_RANKS.index(Rank(start_rank_val))
            end = start + meld.size - 1
            for rank_idx in [start - 1, end + 1]:
                if 0 <= rank_idx < len(MELDABLE_RANKS):
                    rank = MELDABLE_RANKS[rank_idx]
                    for card in groups.get(rank, []):
                        if card.suit == suit:
                            return [card]
        return None

    def _growing_cards(
        self, meld: Meld, groups: dict[Rank, list[Card]]
    ) -> list[Card] | None:
        """Natural cards from hand that extend `meld` without closing it."""
        space = CANASTA_SIZE - meld.size
        if space <= 0:
            return None
        if meld.kind == MeldKind.SET:
            fits = groups.get(Rank(meld.rank_or_suit_anchor), [])
            return fits[:space] or None
        if meld.kind == MeldKind.SEQUENCE:
            suit_val, start_rank_val = meld.rank_or_suit_anchor.split(":")
            suit = Suit(suit_val)
            start = MELDABLE_RANKS.index(Rank(start_rank_val))
            end = start + meld.size - 1
            for rank_idx in [start - 1, end + 1]:
                if 0 <= rank_idx < len(MELDABLE_RANKS):
                    rank = MELDABLE_RANKS[rank_idx]
                    for card in groups.get(rank, []):
                        if card.suit == suit:
                            return [card]
        return None

    def _best_new_set(
        self,
        groups: dict[Rank, list[Card]],
        wilds: list[Card],
        *,
        allow_wild: bool,
    ) -> list[Card] | None:
        best: list[Card] | None = None
        best_val = -1
        for cards in groups.values():
            candidate: list[Card] | None = None
            if len(cards) >= 3:
                candidate = cards[:CANASTA_SIZE]
            elif allow_wild and len(cards) == 2 and wilds:
                candidate = [*cards, wilds[0]]
            if candidate:
                val = sum(c.point_value for c in candidate)
                if val > best_val:
                    best_val = val
                    best = candidate
        return best

    def _best_new_set_advanced(
        self,
        groups: dict[Rank, list[Card]],
        wilds: list[Card],
        deal: DealState,
        player_id: str,
    ) -> list[Card] | None:
        """Prefer ranks with the most copies; avoid duplicating an existing open meld;
        spend twos before jokers."""
        team_id = deal.player_team[player_id]
        team = deal.teams[team_id]
        cheap_wilds = [w for w in wilds if w.rank != Rank.JOKER]

        best: list[Card] | None = None
        best_score = -1

        for rank, cards in groups.items():
            # Skip if we already have an open (unclosed) meld for this rank.
            if any(
                m.kind == MeldKind.SET
                and m.rank_or_suit_anchor == rank.value
                and not m.is_closed
                for m in team.melds
            ):
                continue

            candidate: list[Card] | None = None
            if len(cards) >= 3:
                candidate = cards[:CANASTA_SIZE]
            elif len(cards) == 2:
                if cheap_wilds:
                    candidate = [*cards, cheap_wilds[0]]
                elif len(wilds) >= 2:
                    # Use joker only if we have 2+ wilds (keep one spare).
                    candidate = [*cards, wilds[0]]

            if candidate:
                score = sum(c.point_value for c in candidate if not c.is_wild)
                score += len(cards) * 8  # bonus: more copies = faster canasta
                if score > best_score:
                    best_score = score
                    best = candidate

        return best

    def _pick_new_meld(
        self,
        groups: dict[Rank, list[Card]],
        wilds: list[Card],
        deal: DealState,
        player_id: str,
    ) -> list[Card] | None:
        """Hook for step 4 of _opened_act. Subclasses can override to also try sequences."""
        return self._best_new_set_advanced(groups, wilds, deal, player_id)

    def _best_new_sequence(
        self,
        deal: DealState,
        player_id: str,
        groups: dict[Rank, list[Card]],
        wilds: list[Card],
    ) -> list[Card] | None:
        """Find the best pure (no-gap) 3+ card sequence to start.

        Only considers runs with zero wildcards — wilds are too valuable to
        spend on gaps when a set canasta is the more reliable path. A pure run
        of 3+ consecutive same-suit naturals is worth laying down immediately.
        Skips suits where an open sequence meld already exists.
        """
        team_id = deal.player_team[player_id]
        team = deal.teams[team_id]

        best: list[Card] | None = None
        best_score = -1.0

        for suit in Suit:
            # One natural card per rank index for this suit
            have: dict[int, Card] = {}
            for rank_idx, rank in enumerate(MELDABLE_RANKS):
                for card in groups.get(rank, []):
                    if card.suit == suit:
                        have[rank_idx] = card
                        break

            if len(have) < 3:
                continue  # need ≥3 naturals for a no-gap sequence

            # Ranges already covered by open sequence melds of this suit
            open_seq: list[tuple[int, int]] = []
            for m in team.melds:
                if m.kind == MeldKind.SEQUENCE and not m.is_closed:
                    sv, srk = m.rank_or_suit_anchor.split(":")
                    if Suit(sv) == suit:
                        si = MELDABLE_RANKS.index(Rank(srk))
                        open_seq.append((si, si + m.size))

            # Find all maximal contiguous natural runs for this suit
            sorted_idxs = sorted(have.keys())
            run_start = sorted_idxs[0]
            run = [sorted_idxs[0]]
            for prev, cur in zip(sorted_idxs, sorted_idxs[1:]):
                if cur == prev + 1:
                    run.append(cur)
                else:
                    # Emit the run we just finished
                    if len(run) >= 3:
                        end = run[-1] + 1
                        if not any(s < end and e > run[0] for s, e in open_seq):
                            cards = [have[i] for i in run[:CANASTA_SIZE]]
                            sc = sum(c.point_value for c in cards) + len(cards) * 8
                            if sc > best_score:
                                best_score = sc
                                best = cards
                    run = [cur]
                    run_start = cur
            # Emit last run
            if len(run) >= 3:
                end = run[-1] + 1
                if not any(s < end and e > run[0] for s, e in open_seq):
                    cards = [have[i] for i in run[:CANASTA_SIZE]]
                    sc = sum(c.point_value for c in cards) + len(cards) * 8
                    if sc > best_score:
                        best_score = sc
                        best = cards

        return best

    def _team_sequence_lookahead(
        self, deal: DealState, team_id: str, card: Card
    ) -> bool:
        """True if this card is within ±2 ranks of any open team sequence end.

        Protects cards that aren't the immediate extension but will become
        useful once the adjacent slot is filled — keeps the human's run alive.
        """
        if card.is_wild or card.is_three:
            return False
        for meld in deal.teams[team_id].melds:
            if meld.kind != MeldKind.SEQUENCE or meld.is_closed:
                continue
            sv, srk = meld.rank_or_suit_anchor.split(":")
            if Suit(sv) != card.suit:
                continue
            si = MELDABLE_RANKS.index(Rank(srk))
            ei = si + meld.size - 1
            ci = next(
                (i for i, r in enumerate(MELDABLE_RANKS) if r == card.rank), -1
            )
            if ci < 0:
                continue
            # within 2 ranks of either end (but not already IN the sequence)
            if (si - 2 <= ci < si) or (ei < ci <= ei + 2):
                return True
        return False

    # ── STEAL ─────────────────────────────────────────────────────────────────

    def _find_steal(
        self, deal: DealState, player_id: str, groups: dict[Rank, list[Card]]
    ) -> tuple[str, dict] | None:
        own_team_id = deal.player_team[player_id]
        for team_id, table in deal.teams.items():
            if team_id == own_team_id:
                continue
            for meld in table.melds:
                if meld.kind == MeldKind.WILD_CANASTA:
                    continue
                for pos, card in enumerate(meld.slots):
                    if card is None or not card.is_wild:
                        continue
                    replacement = self._find_replacement(
                        deal, own_team_id, meld, pos, groups
                    )
                    if replacement:
                        return "steal_wild", {
                            "meld_id": meld.id,
                            "wild_card_id": card.id,
                            "replacement_card_id": replacement.id,
                        }
        return None

    def _find_replacement(
        self,
        deal: DealState,
        own_team_id: str,
        meld: Meld,
        pos: int,
        groups: dict[Rank, list[Card]],
    ) -> Card | None:
        if meld.kind == MeldKind.SET:
            candidates = groups.get(Rank(meld.rank_or_suit_anchor), [])
        else:
            suit_val, start_rank_val = meld.rank_or_suit_anchor.split(":")
            suit = Suit(suit_val)
            start = MELDABLE_RANKS.index(Rank(start_rank_val))
            required = MELDABLE_RANKS[start + pos]
            candidates = [c for c in groups.get(required, []) if c.suit == suit]

        if len(candidates) != 1:
            return None  # keep pairs for own melds
        card = candidates[0]
        if self._fits_team_meld(deal, own_team_id, card):
            return None
        return card

    # ── DISCARD ───────────────────────────────────────────────────────────────

    def _choose_discard(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        hand = deal.hands[player_id]
        team_id = deal.player_team[player_id]

        black = next((c for c in hand if c.is_black_three), None)
        if black:
            return "discard", {"card_id": black.id}

        candidates = [c for c in hand if not c.is_wild and not c.is_three]
        if not candidates:
            candidates = [c for c in hand if not c.is_red_three] or list(hand)

        groups = _naturals_by_rank(hand)

        def discard_score(card: Card) -> float:
            if card.is_wild or card.is_red_three:
                return float("inf")

            score = 0.0
            copies = len(groups.get(card.rank, []))

            if copies >= 3:
                score -= 5    # safe: keep the pair
            elif copies == 2:
                score += 25   # costly to break a pair
            else:
                score -= 10   # singleton — happy to discard

            if self._fits_team_meld(deal, team_id, card):
                score += 35
            elif self._team_sequence_lookahead(deal, team_id, card):
                score += 15  # softer protection: useful in 1-2 turns

            # KEY IMPROVEMENT: penalise cards opponents' open melds want.
            danger = self._opponent_danger(deal, team_id, card)
            score += danger * 20

            score += card.point_value * 0.2  # slight preference for low-value trash
            return score

        victim = min(candidates, key=discard_score)
        return "discard", {"card_id": victim.id}

    def _opponent_danger(
        self, deal: DealState, own_team_id: str, card: Card
    ) -> float:
        """How urgently opponents want this card (0 = safe)."""
        danger = 0.0
        for team_id, team in deal.teams.items():
            if team_id == own_team_id:
                continue
            for meld in team.melds:
                if meld.is_closed:
                    continue
                if meld.kind == MeldKind.SET:
                    if card.rank == Rank(meld.rank_or_suit_anchor):
                        # Extra weight when they're close to a canasta.
                        danger += 1.5 if meld.size >= 5 else 1.0
                elif meld.kind == MeldKind.SEQUENCE:
                    suit_val, start_rank_val = meld.rank_or_suit_anchor.split(":")
                    suit = Suit(suit_val)
                    start = MELDABLE_RANKS.index(Rank(start_rank_val))
                    end = start + meld.size - 1
                    if card.suit == suit:
                        extends = (
                            start > 0 and card.rank == MELDABLE_RANKS[start - 1]
                        ) or (
                            end < len(MELDABLE_RANKS) - 1
                            and card.rank == MELDABLE_RANKS[end + 1]
                        )
                        if extends:
                            danger += 1.3 if meld.size >= 5 else 0.8
        return danger

    # ── OPPONENT PRESSURE ─────────────────────────────────────────────────────

    def _opponent_near_canasta(self, deal: DealState, own_team_id: str) -> bool:
        """True when any opponent meld is one card away from closing."""
        for team_id, team in deal.teams.items():
            if team_id == own_team_id:
                continue
            for meld in team.melds:
                if not meld.is_closed and meld.size >= 6:
                    return True
        return False

    # ── OPENING ───────────────────────────────────────────────────────────────

    def _opening_plan(
        self, cards: list[Card], needed: int, team: TeamTable
    ) -> list[list[Card]] | None:
        groups = _naturals_by_rank(cards)
        wilds = _wilds_of(cards)

        melds: list[list[Card]] = []
        pairs: list[list[Card]] = []
        for cs in sorted(
            groups.values(), key=lambda cs: -_set_value(cs[:CANASTA_SIZE])
        ):
            if len(cs) >= 3:
                melds.append(cs[:CANASTA_SIZE])
            elif len(cs) == 2:
                pairs.append(cs)

        def total() -> int:
            return sum(_set_value(m) for m in melds)

        if total() < max(needed, 1):
            for pair in sorted(pairs, key=lambda cs: -cs[0].point_value):
                if not wilds or total() >= needed:
                    break
                melds.append([*pair, wilds.pop(0)])

        while total() < needed and wilds and melds:
            wild = wilds.pop()
            target = next(
                (
                    m
                    for m in melds
                    if len(m) < CANASTA_SIZE
                    and sum(1 for c in m if c.is_wild) + 1
                    <= sum(1 for c in m if not c.is_wild)
                ),
                None,
            )
            if target is None:
                break
            target.append(wild)

        if not melds or total() < needed:
            return None

        used = {c.id for m in melds for c in m}
        leftover = [c for c in cards if c.id not in used]
        plan_closes = any(len(m) >= CANASTA_SIZE for m in melds)
        team_has_canasta = any(m.is_closed for m in team.melds)
        if not leftover and not plan_closes and not team_has_canasta:
            trimmed = melds[:-1]
            if not trimmed or sum(_set_value(m) for m in trimmed) < needed:
                return None
            melds = trimmed

        return melds

    # ── SHARED HELPERS ────────────────────────────────────────────────────────

    def _fits_team_meld(self, deal: DealState, team_id: str, card: Card) -> bool:
        for meld in deal.teams[team_id].melds:
            if meld.is_closed:
                continue
            if meld.kind == MeldKind.SET and card.rank.value == meld.rank_or_suit_anchor:
                return True
            if meld.kind == MeldKind.SEQUENCE:
                suit_val, start_rank_val = meld.rank_or_suit_anchor.split(":")
                suit = Suit(suit_val)
                start = MELDABLE_RANKS.index(Rank(start_rank_val))
                end = start + meld.size - 1
                if card.suit == suit:
                    if start > 0 and card.rank == MELDABLE_RANKS[start - 1]:
                        return True
                    if end < len(MELDABLE_RANKS) - 1 and card.rank == MELDABLE_RANKS[end + 1]:
                        return True
        return False

    def _may_spend(
        self,
        deal: DealState,
        player_id: str,
        used_ids: set[str],
        *,
        closes_canasta: bool,
        mandatory: bool = False,
    ) -> bool:
        hand = deal.hands[player_id]
        team = deal.team_of(player_id)
        rest = [c for c in hand if c.id not in used_ids]
        team_has_canasta = closes_canasta or any(m.is_closed for m in team.melds)

        if not rest:
            return team_has_canasta
        if all(c.is_three for c in rest):
            return True
        if mandatory or closes_canasta or team_has_canasta:
            return True
        rest_playable = sum(1 for c in rest if not c.is_three)
        return rest_playable >= self.HAND_FLOOR


# ── PIMC helpers ──────────────────────────────────────────────────────────────


def _clone_deal(
    deal: DealState,
    new_hands: dict[str, list[Card]],
    new_deck: list[Card],
) -> DealState:
    """Cheap structural copy of DealState — Cards are frozen so only containers
    are duplicated.  Used by EliteBotStrategy for Monte Carlo determinisation."""
    new_teams: dict[str, TeamTable] = {}
    for tid, table in deal.teams.items():
        new_melds = [
            Meld(
                id=m.id,
                team_id=m.team_id,
                kind=m.kind,
                rank_or_suit_anchor=m.rank_or_suit_anchor,
                slots=list(m.slots),
            )
            for m in table.melds
        ]
        new_teams[tid] = TeamTable(
            team_id=table.team_id,
            melds=new_melds,
            is_opened=table.is_opened,
            turn_accumulator=table.turn_accumulator,
        )
    return DealState(
        deck=list(new_deck),
        discard_pile=list(deal.discard_pile),
        teams=new_teams,
        hands={pid: list(h) for pid, h in new_hands.items()},
        thresholds=dict(deal.thresholds),
        player_order=list(deal.player_order),
        player_team=dict(deal.player_team),
        turn_state=deal.turn_state,
        penalties=dict(deal.penalties),
        deal_over=deal.deal_over,
        exit_team_id=deal.exit_team_id,
        exit_type=deal.exit_type,
    )


def _fallback_move(deal: DealState, player_id: str) -> tuple[str, dict]:
    turn = deal.turn_state
    if turn.phase == TurnPhase.DRAW:
        return "draw_deck", {}
    if (
        turn.must_meld_after_pickup
        and turn.melds_created_this_turn == 0
        and not turn.pending_penalty
    ):
        return "concede_penalty", {}
    hand = deal.hands[player_id]
    if hand:
        return "discard", {"card_id": hand[0].id}
    return "concede_penalty", {}


def _exec_intent(deal: DealState, player_id: str, intent: str, data: dict) -> DealState:
    """Convert intent → engine Action and apply it, returning the new state."""
    from app.engine.actions import (
        AddToMeld,
        ConcedePenalty,
        CreateMeld,
        Discard,
        StealWild,
    )
    match intent:
        case "draw_deck":       action = DrawDeck()
        case "draw_discard":    action = DrawDiscard()
        case "create_meld":     action = CreateMeld(card_ids=data["card_ids"], wild_side=data.get("wild_side","low"))
        case "add_to_meld":     action = AddToMeld(meld_id=data["meld_id"], card_ids=data["card_ids"], wild_side=data.get("wild_side","low"))
        case "steal_wild":      action = StealWild(meld_id=data["meld_id"], wild_card_id=data["wild_card_id"], replacement_card_id=data["replacement_card_id"])
        case "discard":         action = Discard(card_id=data["card_id"])
        case "concede_penalty": action = ConcedePenalty()
        case _:                 raise ValueError(f"unknown intent {intent!r}")
    return apply_action(deal, player_id, action)


class SequenceBotStrategy(AdvancedBotStrategy):
    """AdvancedBotStrategy that can also create sequence melds.

    Overrides _pick_new_meld to try both sets and sequences and pick whichever
    scores higher (more raw card points laid down this turn).
    """

    def _pick_new_meld(
        self,
        groups: dict[Rank, list[Card]],
        wilds: list[Card],
        deal: DealState,
        player_id: str,
    ) -> list[Card] | None:
        new_set = self._best_new_set_advanced(groups, wilds, deal, player_id)
        new_seq = self._best_new_sequence(deal, player_id, groups, wilds)

        if new_set and new_seq:
            # Prefer a pure sequence only when it lays down more cards — a
            # longer run gets closer to canasta without spending any wildcards.
            set_naturals = sum(1 for c in new_set if not c.is_wild)
            seq_naturals = len(new_seq)  # sequences from _best_new_sequence are always pure
            if seq_naturals > set_naturals:
                return new_seq
            return new_set

        return new_set or new_seq


class EliteBotStrategy:
    """Tournament-strength Canasta bot.

    Built on top of AdvancedBotStrategy with three major additions:

    1. **PIMC draw decisions** — Perfect-Information Monte Carlo for pick/no-pick.
       Samples N possible distributions of unseen cards (opponent hands + deck),
       runs a mini-rollout of our own ACT phase in each sample, then evaluates.
       Hard-gates pile taking against the real hand first to prevent illegal
       mandatory-meld situations that would cost -1000.

    2. **Strategic exit timing** — goes out (dirty) as soon as the calculation
       shows it outperforms continuing: exit_bonus + trapped_opponent_penalty
       vs. expected value of N more turns.

    3. **Dead-card discard safety** — ranks where most copies are already
       visible (melds + discard + own hand) are treated as ultra-safe to
       discard; the opponent is unlikely to hold or need them.
    """

    N_SAMPLES = 24          # MC samples per draw decision (was 20)
    N_DISCARD_SAMPLES = 8   # MC samples per discard candidate
    COPIES_PER_RANK = 8     # 4 suits × 2 decks

    def __init__(self, rng_seed: int | None = None) -> None:
        # Use class-level constants so subclasses that override N_SAMPLES get
        # the right count without needing to override __init__ as well.
        # rng_seed is None by default (unseeded, matches prior behavior) —
        # pass a fixed int for reproducible A/B benchmarking, since PIMC
        # sample counts consume different amounts of randomness and would
        # otherwise make two configs diverge in game trajectory, not just outcome.
        self._n = self.N_SAMPLES
        self._n_discard = self.N_DISCARD_SAMPLES
        self._adv = AdvancedBotStrategy()
        self._rng = random.Random(rng_seed)

    def choose_intent(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        turn = deal.turn_state
        if turn.phase == TurnPhase.DRAW:
            return self._draw(deal, player_id)
        if turn.phase == TurnPhase.ACT:
            return self._act(deal, player_id)
        raise RuntimeError(f"EliteBotStrategy: no move for phase {turn.phase!r}")

    # ── DRAW: PIMC ─────────────────────────────────────────────────────────────

    def _draw(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        pile = deal.discard_pile
        if not pile or pile[-1].is_three:
            return "draw_deck", {}

        # Hard gate: only consider taking the pile when the REAL hand can
        # actually satisfy the mandatory-meld requirement afterwards.
        # Without this check, MC noise can cause -1000 penalties every turn.
        if not self._can_handle_pickup(deal, player_id):
            return "draw_deck", {}

        # Very large pile — take it (legality already verified above).
        if len(pile) >= 9:
            return "draw_discard", {}

        ev_deck = self._mc_ev(deal, player_id, take_pile=False)
        ev_pile = self._mc_ev(deal, player_id, take_pile=True)

        if ev_pile > ev_deck:
            return "draw_discard", {}
        return "draw_deck", {}

    def _mc_ev(self, deal: DealState, player_id: str, take_pile: bool) -> float:
        """Average positional value after this draw action over N determinisations.

        Runs a mini-rollout of our own ACT phase (using AdvancedBot) before
        evaluating so that the pile's meld potential is captured properly.
        In mid/late game (deck < 40) also simulates 1 full opponent-reaction
        turn to capture threats like near-canasta melds.
        NOTE: apply_action mutates the deal in-place, so we must determinize
        separately for each action — shared worlds are NOT safe.
        """
        total = 0.0
        n_ok = 0
        # 1-turn opponent lookahead only mid/late game where threats crystallise.
        n_extra = 0 if len(deal.deck) >= 40 else 1

        for _ in range(self._n):
            det = self._determinize(deal, player_id)
            action = DrawDiscard() if take_pile else DrawDeck()

            try:
                sim = apply_action(det, player_id, action)
            except (IllegalActionError, Exception):
                if take_pile:
                    total -= 800   # illegal pile take → likely -1000 penalty
                    n_ok += 1
                continue

            # Mini-rollout: simulate our own ACT phase so the value function
            # sees post-meld table state rather than a bloated pre-meld hand.
            sim = self._rollout_own_act(sim, player_id)
            if n_extra:
                sim = self._multi_turn_rollout(sim, player_id, n_extra)

            total += self._fast_value(sim, player_id)
            n_ok += 1

        return total / n_ok if n_ok else 0.0

    def _rollout_own_act(
        self, deal: DealState, player_id: str, max_steps: int = 10
    ) -> DealState:
        """Simulate our own ACT phase up to (but not including) discard.

        Stopping before discard evaluates the post-meld position, capturing
        the value of opened melds without the noise of a simulated discard choice.
        """
        sim = deal
        for _ in range(max_steps):
            if sim.deal_over:
                break
            turn = sim.turn_state
            if turn.current_player_id != player_id:
                break
            if turn.phase != TurnPhase.ACT:
                break
            try:
                intent, data = self._adv._choose_act(sim, player_id)
                if intent == "discard":
                    break  # stop before discard; evaluate post-meld position
                sim = _exec_intent(sim, player_id, intent, data)
                if intent == "concede_penalty":
                    break
            except Exception:
                break
        return sim

    def _determinize(self, deal: DealState, player_id: str) -> DealState:
        """Redistribute unseen cards (deck + all other hands) randomly while
        preserving own hand and all public information."""
        unseen: list[Card] = list(deal.deck)
        for pid, cards in deal.hands.items():
            if pid != player_id:
                unseen.extend(cards)
        self._rng.shuffle(unseen)

        new_hands: dict[str, list[Card]] = {player_id: list(deal.hands[player_id])}
        offset = 0
        for pid in deal.player_order:
            if pid == player_id:
                continue
            size = len(deal.hands[pid])
            new_hands[pid] = unseen[offset : offset + size]
            offset += size

        return _clone_deal(deal, new_hands, unseen[offset:])

    def _fast_value(self, deal: DealState, player_id: str) -> float:
        """Score: my_team_value − opp_team_value (purely positional)."""
        my_team = deal.player_team[player_id]
        opp_team = next(t for t in deal.teams if t != my_team)

        # 1.0 = fresh deck, 0.0 = exhausted; used to scale late-game urgency.
        deck_frac = len(deal.deck) / 108.0

        def team_val(team_id: str) -> float:
            table = deal.teams[team_id]
            hand_cards = [
                c
                for pid, cards in deal.hands.items()
                if deal.player_team[pid] == team_id
                for c in cards
            ]

            has_canasta = any(m.is_closed for m in table.melds)
            open_melds  = [m for m in table.melds if not m.is_closed]

            # Meld table value.  Without a canasta the team cannot go out, so
            # locked-in table points are only ~25% as actionable — they count
            # at end-of-deal but expose the team to opponent initiative risk.
            raw_pts = sum(m.point_value for m in table.melds)
            table_pts = raw_pts if has_canasta else raw_pts * 0.25

            # Canasta bonuses already secured
            canasta_bonus = sum(m.canasta_bonus for m in table.melds)

            # Future value of open melds: each card already on table ~18 pts
            open_progress = sum(m.size * 18 for m in open_melds)

            # Convex reward for melds close to canasta completion (6/7 >> 3/7)
            canasta_completion = sum(
                (m.size / CANASTA_SIZE) ** 2 * 60 for m in open_melds
            )

            # Hand penalty scales with game progress:
            #   early (deck_frac≈1): 0.35 × face   (most cards will be melded)
            #   late  (deck_frac≈0): 1.00 × face   (stranded cards will be lost)
            non_three = [c for c in hand_cards if not c.is_three and not c.is_wild]
            penalty_mult = 0.35 + 0.65 * (1.0 - deck_frac)
            hand_penalty = -sum(c.point_value for c in non_three) * penalty_mult

            # Pair/triple potential in hand (valued at 15 per card in group)
            groups: dict[Rank, int] = {}
            for c in hand_cards:
                if not c.is_wild and not c.is_three:
                    groups[c.rank] = groups.get(c.rank, 0) + 1
            pair_pot = sum(cnt * 15 for cnt in groups.values() if cnt >= 2)

            # Wilds: very valuable early (2.2×), still valuable late (1.8×)
            wild_mult = 1.8 + 0.4 * deck_frac
            wild_bonus = sum(c.point_value for c in hand_cards if c.is_wild) * wild_mult

            # Accumulated penalties (e.g. -1000 from ConcedePenalty)
            accrued_penalty = deal.penalties.get(team_id, 0)

            return (
                table_pts
                + canasta_bonus
                + open_progress
                + canasta_completion
                + hand_penalty
                + pair_pot
                + wild_bonus
                + accrued_penalty
            )

        return team_val(my_team) - team_val(opp_team)

    def _can_handle_pickup(self, deal: DealState, player_id: str) -> bool:
        """True when the real hand can satisfy the mandatory meld after taking
        the pile.  This is a hard gate — MC is never called if False."""
        team = deal.team_of(player_id)
        hand = deal.hands[player_id]
        pile = deal.discard_pile

        if team.is_opened:
            # Need to create at least one new meld from hand + pile.
            combined = [*hand, *pile]
            groups = _naturals_by_rank(combined)
            wilds = _wilds_of(combined)
            # New set (3 naturals, or 2 naturals + 1 wild)
            if self._adv._best_new_set(groups, wilds, allow_wild=True) is not None:
                return True
            # Extend any existing open meld
            combined_groups = _naturals_by_rank(combined)
            return any(
                self._adv._growing_cards(m, combined_groups) is not None
                or self._adv._closing_cards(m, combined_groups, wilds) is not None
                for m in team.melds if not m.is_closed
            )

        # Unopened: need an opening plan that covers the threshold.
        # The top card of the pile must be used in one of the melds
        # (Canasta rule: you have to meld the card you pick up).
        team_id = deal.player_team[player_id]
        needed = deal.thresholds[team_id] - team.turn_accumulator
        top = pile[-1]
        # AdvancedBot's _should_take_pile already does this check properly.
        return self._adv._should_take_pile(deal, player_id)

    def _can_meld_now(self, deal: DealState, player_id: str) -> bool:
        """Quick check: can mandatory meld be satisfied from current hand?"""
        team = deal.team_of(player_id)
        hand = deal.hands[player_id]
        groups = _naturals_by_rank(hand)
        wilds = _wilds_of(hand)

        if team.is_opened:
            for meld in team.melds:
                if not meld.is_closed:
                    if self._adv._growing_cards(meld, groups):
                        return True
                    if self._adv._closing_cards(meld, groups, wilds):
                        return True
            return self._adv._best_new_set(groups, wilds, allow_wild=True) is not None

        team_id = deal.player_team[player_id]
        needed = deal.thresholds[team_id] - team.turn_accumulator
        return self._adv._opening_plan(hand, needed, team) is not None

    # ── ACT: AdvancedBot + strategic exit + dead-card discard ─────────────────

    def _act(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        team = deal.team_of(player_id)
        turn = deal.turn_state
        hand = deal.hands[player_id]

        # ── Exit-timing: bail out when it's strategically correct to do so.
        # Only on the FIRST ACT call this turn (before any meld).
        # Guard: must have no wilds in hand (else we'd accidentally discard one)
        # and at least 1 normal card to actually discard.
        if (
            any(m.is_closed for m in team.melds)
            and not turn.must_meld_after_pickup
            and turn.melds_created_this_turn == 0
        ):
            wilds_h = _wilds_of(hand)
            non_three = [c for c in hand if not c.is_three and not c.is_wild]
            if (
                not wilds_h
                and 1 <= len(non_three) <= 2
                and self._should_exit_now(deal, player_id)
            ):
                # Try to close an existing meld first, then discard to exit.
                groups = _naturals_by_rank(hand)
                for meld in sorted(team.melds, key=lambda m: -m.size):
                    if meld.is_closed:
                        continue
                    take = self._adv._closing_cards(meld, groups, [])
                    if take and self._adv._may_spend(
                        deal, player_id, {c.id for c in take}, closes_canasta=True
                    ):
                        return "add_to_meld", {
                            "meld_id": meld.id,
                            "card_ids": [c.id for c in take],
                        }
                return self._choose_discard_elite(deal, player_id)

        # ── Normal play (delegate to AdvancedBotStrategy)
        intent, data = self._adv._choose_act(deal, player_id)
        if intent == "discard":
            return self._choose_discard_elite(deal, player_id)
        return intent, data

    def _should_exit_now(self, deal: DealState, player_id: str) -> bool:
        """True when going out now is better than giving opponents more turns."""
        team_id = deal.player_team[player_id]
        opp_team = next(t for t in deal.teams if t != team_id)
        opp_table = deal.teams[opp_team]
        my_table  = deal.teams[team_id]

        # Exit urgently: opponent one card from canasta
        if any(m.size >= 6 for m in opp_table.melds if not m.is_closed):
            return True

        # Exit threshold: more urgent when opponent is close to winning the match
        opp_thresh = deal.thresholds.get(opp_team, 30)
        deck_threshold = 25 if opp_thresh >= 120 else 18
        if len(deal.deck) <= deck_threshold:
            return True

        # Exit when we hold a material positional advantage in closed melds
        my_closed_pts  = sum(m.point_value for m in my_table.melds  if m.is_closed)
        opp_closed_pts = sum(m.point_value for m in opp_table.melds if m.is_closed)
        # Lower advantage threshold when opponent is in late-match territory
        advantage_needed = 80 if opp_thresh >= 90 else 100
        if my_closed_pts > opp_closed_pts + advantage_needed:
            return True

        return False

    # ── DISCARD: dead-card saturation layer ────────────────────────────────────

    def _choose_discard_elite(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        hand = deal.hands[player_id]
        team_id = deal.player_team[player_id]

        black = next((c for c in hand if c.is_black_three), None)
        if black:
            return "discard", {"card_id": black.id}

        candidates = [c for c in hand if not c.is_wild and not c.is_three]
        if not candidates:
            return self._adv._choose_discard(deal, player_id)

        groups = _naturals_by_rank(hand)
        saturation = self._rank_saturation(deal, player_id)

        def score(card: Card) -> float:
            copies_in_hand = len(groups.get(card.rank, []))
            if copies_in_hand >= 3:
                s = -5.0
            elif copies_in_hand == 2:
                s = 25.0
            else:
                s = -10.0

            if self._adv._fits_team_meld(deal, team_id, card):
                s += 35.0
            elif self._adv._team_sequence_lookahead(deal, team_id, card):
                s += 15.0

            # Hard block: never feed an opponent's SET meld that is one card from canasta.
            for opp_id, opp_table in deal.teams.items():
                if opp_id == team_id:
                    continue
                for meld in opp_table.melds:
                    if meld.is_closed or meld.size < 6 or meld.kind.name != "SET":
                        continue
                    if card.rank.value == meld.rank_or_suit_anchor:
                        return float("inf")  # absolute ban

            # Combine bayesian danger (board danger × P(opp holds)) with
            # saturation discount (fewer unknown copies = less dangerous).
            b_danger = self._bayesian_danger(deal, team_id, card)
            known = saturation.get(card.rank, 0)
            saturation_discount = max(0.0, (known - 3) / 5)
            s += b_danger * 20.0 * (1.0 - saturation_discount)

            s += card.point_value * 0.2
            return s

        return "discard", {"card_id": min(candidates, key=score).id}

    def _rank_saturation(self, deal: DealState, player_id: str) -> dict[Rank, int]:
        """How many copies of each rank are in known locations
        (own hand + all melds + discard pile)."""
        counts: dict[Rank, int] = {}

        for c in deal.hands[player_id]:
            if not c.is_wild and not c.is_three:
                counts[c.rank] = counts.get(c.rank, 0) + 1

        for team in deal.teams.values():
            for meld in team.melds:
                for c in meld.slots:
                    if c is not None and not c.is_wild and not c.is_three:
                        counts[c.rank] = counts.get(c.rank, 0) + 1

        for c in deal.discard_pile:
            if not c.is_wild and not c.is_three:
                counts[c.rank] = counts.get(c.rank, 0) + 1

        return counts

    def _bayesian_danger(
        self, deal: DealState, own_team_id: str, card: Card
    ) -> float:
        """Board danger weighted by P(opponent holds this rank).

        Uses a hypergeometric approximation to compute P(≥1 opponent holds
        the rank), then multiplies raw board danger by that probability.
        More accurate than flat danger when many copies are already visible.
        """
        if card.is_wild or card.is_three:
            return 0.0

        copies_total = 8   # 4 suits × 2 decks
        visible = 0
        for pid, h in deal.hands.items():
            if deal.player_team[pid] == own_team_id:
                visible += sum(
                    1 for c in h
                    if c.rank == card.rank and not c.is_wild and not c.is_three
                )
        for team in deal.teams.values():
            for meld in team.melds:
                for s in meld.slots:
                    if s is not None and s.rank == card.rank and not s.is_wild:
                        visible += 1
        for c2 in deal.discard_pile:
            if c2.rank == card.rank and not c2.is_wild:
                visible += 1

        unseen_rank  = max(0, copies_total - visible)
        opp_hand_sz  = sum(
            len(h) for pid, h in deal.hands.items()
            if deal.player_team[pid] != own_team_id
        )
        unseen_total = len(deal.deck) + opp_hand_sz

        if unseen_total <= 0 or unseen_rank <= 0:
            p_holds = 0.0
        else:
            p_holds = 1.0 - max(
                0.0,
                (unseen_total - unseen_rank) / unseen_total,
            ) ** opp_hand_sz

        return self._adv._opponent_danger(deal, own_team_id, card) * p_holds

    # ── Shared rollout primitive (also used by FullPIMC / ML subclasses) ────────

    def _multi_turn_rollout(
        self, deal: DealState, player_id: str, n_turns: int
    ) -> DealState:
        """Drive all players with AdvancedBot until player_id's DRAW phase
        appears n_turns more times.  Captures how opponents react to our moves."""
        sim = deal
        own_draws = 0
        cap = n_turns * len(sim.player_order) * 8 + 20

        for _ in range(cap):
            if sim.deal_over:
                break
            pid   = sim.turn_state.current_player_id
            phase = sim.turn_state.phase

            if pid == player_id and phase == TurnPhase.DRAW:
                own_draws += 1
                if own_draws > n_turns:
                    break

            try:
                intent, data = self._adv.choose_intent(sim, pid)
                sim = _exec_intent(sim, pid, intent, data)
            except Exception:
                try:
                    sim = _exec_intent(sim, pid, *_fallback_move(sim, pid))
                except Exception:
                    break

        return sim

    # ── DISCARD: lightweight MC layer (4 samples, 1-turn full lookahead) ────────

    N_DISCARD_SAMPLES_LIGHT = 4   # cheap MC samples (NOT used by Elite._act — heuristic is better)

    def _choose_discard_mc(
        self, deal: DealState, player_id: str
    ) -> tuple[str, dict]:
        """Light Monte Carlo discard for EliteBotStrategy.

        Prefilters to the top 3 heuristic candidates, then ranks them via
        4 MC samples each (1 full opponent-turn lookahead).  Much cheaper than
        FullPIMC's discard but still captures opponent-reaction signal missing
        from the pure heuristic.
        """
        hand = deal.hands[player_id]

        black = next((c for c in hand if c.is_black_three), None)
        if black:
            return "discard", {"card_id": black.id}

        candidates = [c for c in hand if not c.is_wild and not c.is_three]
        if not candidates:
            return self._adv._choose_discard(deal, player_id)

        team_id = deal.player_team[player_id]
        groups  = _naturals_by_rank(hand)
        sat     = self._rank_saturation(deal, player_id)

        def _heur(card: Card) -> float:
            copies = len(groups.get(card.rank, []))
            s = 25.0 * (copies == 2) - 5.0 * (copies >= 3) - 10.0 * (copies == 1)
            if self._adv._fits_team_meld(deal, team_id, card):
                s += 35.0
            elif self._adv._team_sequence_lookahead(deal, team_id, card):
                s += 15.0
            danger = self._adv._opponent_danger(deal, team_id, card)
            known  = sat.get(card.rank, 0)
            s += danger * 20.0 * max(0.0, 1.0 - (known - 3) / 5.0)
            s += card.point_value * 0.2
            return s

        contenders = sorted(candidates, key=_heur)[:3]
        if len(contenders) == 1:
            return "discard", {"card_id": contenders[0].id}

        best_card = contenders[0]
        best_ev   = float("-inf")
        for card in contenders:
            total = 0.0
            n_ok  = 0
            for _ in range(self.N_DISCARD_SAMPLES_LIGHT):
                det = self._determinize(deal, player_id)
                try:
                    sim = _exec_intent(det, player_id, "discard", {"card_id": card.id})
                except Exception:
                    continue
                sim = self._multi_turn_rollout(sim, player_id, n_turns=1)
                total += self._fast_value(sim, player_id)
                n_ok  += 1
            ev = total / n_ok if n_ok else float("-inf")
            if ev > best_ev:
                best_ev   = ev
                best_card = card

        return "discard", {"card_id": best_card.id}


class FullPIMCBotStrategy(EliteBotStrategy):
    """EliteBotStrategy + three algorithmic upgrades (no ML):

    1. Multi-turn rollout — DRAW-phase MC now simulates N_LOOKAHEAD_TURNS full
       player turns (all 4 players) rather than stopping after our own ACT.
    2. PIMC for DISCARD — each candidate discard card is scored via Monte Carlo
       (N_DISCARD_SAMPLES worlds × 1 opponent turn lookahead) instead of a
       static heuristic score.
    3. Bayesian danger — discard scoring weights board danger by the probability
       that opponents actually hold the rank, not just "is it useful on board".
    """

    N_SAMPLES         = 30   # draw-phase MC samples (Elite=24, FullPIMC must exceed it)
    N_DISCARD_SAMPLES = 14   # MC samples per discard candidate
    N_LOOKAHEAD_TURNS = 2    # full player cycles to simulate in draw MC
    N_DISCARD_TURNS   = 2    # opponent turns to simulate per discard candidate

    # ── Multi-turn rollout ────────────────────────────────────────────────

    def _adaptive_depth(self, deal: DealState, base: int) -> int:
        """Use shallower rollout when the deck is large (low signal, high noise).

        Early game (≥55 cards): 1 turn is sufficient — the position is fluid
        and deeper simulation just amplifies random card-distribution noise.
        Late game (<55 cards): full depth for decisive end-game choices.
        """
        return 1 if len(deal.deck) >= 55 else base

    def _mc_ev(self, deal: DealState, player_id: str, take_pile: bool) -> float:
        """Override: extend rollout beyond own ACT to N_LOOKAHEAD_TURNS turns."""
        total  = 0.0
        n_ok   = 0
        n_turns = self._adaptive_depth(deal, self.N_LOOKAHEAD_TURNS)

        for _ in range(self._n):
            det    = self._determinize(deal, player_id)
            action = DrawDiscard() if take_pile else DrawDeck()

            try:
                sim = apply_action(det, player_id, action)
            except (IllegalActionError, Exception):
                if take_pile:
                    total -= 800
                    n_ok  += 1
                continue

            sim = self._multi_turn_rollout(sim, player_id, n_turns)
            total += self._fast_value(sim, player_id)
            n_ok  += 1

        return total / n_ok if n_ok else 0.0

    # ── PIMC discard ──────────────────────────────────────────────────────

    def _act(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        """Identical to EliteBot's _act but routes the discard through PIMC."""
        team = deal.team_of(player_id)
        turn = deal.turn_state
        hand = deal.hands[player_id]

        if (
            any(m.is_closed for m in team.melds)
            and not turn.must_meld_after_pickup
            and turn.melds_created_this_turn == 0
        ):
            wilds_h   = _wilds_of(hand)
            non_three = [c for c in hand if not c.is_three and not c.is_wild]
            if (
                not wilds_h
                and 1 <= len(non_three) <= 2
                and self._should_exit_now(deal, player_id)
            ):
                groups = _naturals_by_rank(hand)
                for meld in sorted(team.melds, key=lambda m: -m.size):
                    if meld.is_closed:
                        continue
                    take = self._adv._closing_cards(meld, groups, [])
                    if take and self._adv._may_spend(
                        deal, player_id, {c.id for c in take}, closes_canasta=True
                    ):
                        return "add_to_meld", {
                            "meld_id": meld.id,
                            "card_ids": [c.id for c in take],
                        }
                return self._choose_discard_pimc(deal, player_id)

        intent, data = self._adv._choose_act(deal, player_id)
        if intent == "discard":
            return self._choose_discard_pimc(deal, player_id)
        return intent, data

    def _choose_discard_pimc(
        self, deal: DealState, player_id: str
    ) -> tuple[str, dict]:
        """Monte Carlo discard: pick the card that maximises expected positional
        value after one round of opponent responses.

        Pre-filters to the 6 cheapest-looking candidates by heuristic score,
        then uses MC to rank them accurately.
        """
        hand = deal.hands[player_id]

        black = next((c for c in hand if c.is_black_three), None)
        if black:
            return "discard", {"card_id": black.id}

        candidates = [c for c in hand if not c.is_wild and not c.is_three]
        if not candidates:
            return self._choose_discard_elite(deal, player_id)

        team_id = deal.player_team[player_id]
        groups  = _naturals_by_rank(hand)
        sat     = self._rank_saturation(deal, player_id)

        def _heur(card: Card) -> float:
            copies = len(groups.get(card.rank, []))
            s = 25.0 * (copies == 2) - 5.0 * (copies >= 3) - 10.0 * (copies == 1)
            if self._adv._fits_team_meld(deal, team_id, card):
                s += 35.0
            elif self._adv._team_sequence_lookahead(deal, team_id, card):
                s += 15.0
            # Use bayesian danger (board danger × P(opp holds)) + saturation discount
            b_danger = self._bayesian_danger(deal, team_id, card)
            known    = sat.get(card.rank, 0)
            s       += b_danger * 20.0 * max(0.0, 1.0 - (known - 3) / 5.0)
            s       += card.point_value * 0.2
            return s

        # Pre-sort by heuristic, then deduplicate by rank: cards of the same
        # rank are equivalent in set-meld Canasta (same point value, same meld
        # target), so their MC scores are identical — no need to evaluate twice.
        sorted_cands = sorted(candidates, key=_heur)
        seen_ranks: set = set()
        unique_contenders: list[Card] = []
        for c in sorted_cands:
            if c.rank not in seen_ranks:
                unique_contenders.append(c)
                seen_ranks.add(c.rank)
            if len(unique_contenders) == 5:
                break

        if len(unique_contenders) == 1:
            return "discard", {"card_id": unique_contenders[0].id}

        best_card = unique_contenders[0]
        best_ev   = float("-inf")
        for card in unique_contenders:
            ev = self._mc_ev_discard(deal, player_id, card)
            if ev > best_ev:
                best_ev   = ev
                best_card = card

        return "discard", {"card_id": best_card.id}

    def _mc_ev_discard(
        self, deal: DealState, player_id: str, card: Card
    ) -> float:
        """Average positional value after discarding `card` across
        N_DISCARD_SAMPLES determinisations (N_DISCARD_TURNS lookahead each).
        """
        total   = 0.0
        n_ok    = 0
        n_turns = self._adaptive_depth(deal, self.N_DISCARD_TURNS)

        for _ in range(self._n_discard):
            det = self._determinize(deal, player_id)
            try:
                sim = _exec_intent(det, player_id, "discard", {"card_id": card.id})
            except Exception:
                continue
            sim = self._multi_turn_rollout(sim, player_id, n_turns=n_turns)
            total += self._fast_value(sim, player_id)
            n_ok  += 1

        return total / n_ok if n_ok else 0.0

class MLBotStrategy(FullPIMCBotStrategy):
    """FullPIMCBotStrategy + trained positional value function.

    The handcrafted _fast_value heuristic (with its magic coefficients) is
    replaced by an MLP trained on 50k+ self-play game positions.
    Falls back to the heuristic if value_weights.json is missing.
    """

    def __init__(self, rng_seed: int | None = None) -> None:
        super().__init__(rng_seed=rng_seed)
        from app.bots.value_model import load_model
        self._ml_available = load_model()

    def _fast_value(self, deal: DealState, player_id: str) -> float:
        """Adaptive ML/heuristic blend that shifts toward ML as the game matures.

        Early game (deck full): 25% ML — positions are fluid, heuristic more reliable.
        Late game (deck empty): 80% ML — positions stable, model better calibrated.
        Falls back to 100% heuristic if the model is not loaded.
        """
        heuristic = super()._fast_value(deal, player_id)
        if not self._ml_available:
            return heuristic
        from app.bots.value_model import predict_value
        ml_val = predict_value(deal, player_id)
        if ml_val is None:
            return heuristic
        deck_frac = len(deal.deck) / 108.0            # 1.0 = fresh, 0.0 = empty
        ml_weight = 0.25 + 0.40 * (1.0 - deck_frac)  # 0.25 early → 0.65 late
        return ml_weight * ml_val + (1.0 - ml_weight) * heuristic


BOT_STRATEGIES: dict[str, BotStrategy] = {
    "simple":    SimpleBotStrategy(),
    "heuristic": HeuristicBotStrategy(),
    "advanced":  AdvancedBotStrategy(),
    "sequence":  SequenceBotStrategy(),
    "elite":     EliteBotStrategy(),
    "fullpimc":  FullPIMCBotStrategy(),
    "mlbot":     MLBotStrategy(),
}
DEFAULT_BOT_STRATEGY = "mlbot"
