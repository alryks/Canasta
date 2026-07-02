// The engine reports action_error reasons as English developer strings
// (backend/app/engine/*). Players see them in the error toast, so map every
// known message to Russian here; unknown ones fall through verbatim.

const SUIT_RU: Record<string, string> = {
  SPADES: 'пики',
  HEARTS: 'червы',
  DIAMONDS: 'бубны',
  CLUBS: 'трефы',
}

function suitRu(raw: string): string {
  return SUIT_RU[raw] ?? raw
}

const TRANSLATIONS: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/^deal is (already|not) over/, () => 'Сдача уже завершена'],
  [/^it is not .+'s turn$/, () => 'Сейчас не ваш ход'],
  [/^cards not in hand/, () => 'Этих карт уже нет в руке'],
  [/^deck is empty$/, () => 'Колода пуста'],
  [/^discard pile is empty$/, () => 'Стопка сброса пуста'],
  [/^no such (opponent )?meld/, () => 'Такой комбинации нет на столе'],
  [/^cannot draw_deck during phase/, () => 'Сейчас нельзя брать карту из колоды'],
  [/^cannot draw_discard during phase/, () => 'Сейчас нельзя брать стопку сброса'],
  [
    /^cannot take discard pile when a three is on top$/,
    () => 'Нельзя брать сброс, когда сверху лежит тройка',
  ],
  [
    /^cannot create a meld during phase/,
    () => 'Выкладывать можно только после взятия карты',
  ],
  [/^cannot concede_penalty during phase/, () => 'Сейчас нельзя принять штраф'],
  [/^cannot discard during phase/, () => 'Сейчас нельзя сбрасывать'],
  [
    /^discard blocked/,
    () =>
      'Нельзя закончить ход: взяв стопку сброса, нужно выложить новую комбинацию (или принять штраф −1000)',
  ],
  [
    /^cannot go out/,
    () => 'Нельзя выйти: рука не пуста или у команды нет собранной канасты',
  ],
  [/^cannot end_turn during phase/, () => 'Ход ещё не завершён'],
  [/^cannot skip turn/, () => 'Сдача уже завершена — пропускать нечего'],
  [/is not the current player$/, () => 'Сейчас ходит другой игрок'],
  [/^a new meld needs at least 3 cards$/, () => 'Для новой комбинации нужно минимум 3 карты'],
  [
    /^wild cards cannot outnumber natural cards/,
    () => 'Козырей в комбинации не может быть больше, чем натуральных карт',
  ],
  [
    /^cards do not form a valid set/,
    () =>
      'Выбранные карты не образуют ни сет (одно достоинство), ни ряд (одна масть по порядку)',
  ],
  [
    /^a sequence needs at least one natural card$/,
    () => 'В ряду нужна хотя бы одна натуральная карта',
  ],
  [
    /^all natural cards in a sequence must share the same suit$/,
    () => 'Все карты ряда должны быть одной масти',
  ],
  [
    /^a sequence cannot repeat the same rank twice$/,
    () => 'В ряду не может быть двух карт одного достоинства',
  ],
  [
    /^not enough wild cards to bridge the gaps/,
    () => 'Не хватает козырей, чтобы закрыть пропуски в ряду',
  ],
  [
    /^sequence would have to run past 4 or past Ace$/,
    () => 'Ряд вышел бы за пределы от 4 до туза',
  ],
  [
    /^cannot add cards to another team's meld$/,
    () => 'Нельзя докладывать в комбинацию соперников',
  ],
  [
    /^cannot add cards to a completed canasta/,
    () => 'Канаста уже собрана — докладывать в неё нельзя',
  ],
  [/^no cards to add$/, () => 'Не выбраны карты для докладывания'],
  [/^a canasta cannot exceed 7 cards$/, () => 'В канасте не может быть больше 7 карт'],
  [
    /^a wild canasta can only take wild cards$/,
    () => 'В козырную канасту можно докладывать только козыри',
  ],
  [
    /^only rank (\S+) cards fit into this set$/,
    (m) => `В этот сет подходят только карты достоинства ${m[1]}`,
  ],
  [
    /^only (\S+) cards fit into this sequence$/,
    (m) => `В этот ряд подходят только карты масти «${suitRu(m[1])}»`,
  ],
  [
    /^cannot steal a wild from your own team's meld$/,
    () => 'Нельзя красть козырь из комбинации своей команды',
  ],
  [/^cannot steal from a wild canasta$/, () => 'Из козырной канасты красть нельзя'],
  [
    /^the replacement card must be a natural card$/,
    () => 'Заменить козырь можно только натуральной картой',
  ],
  [/^wild card not found in this meld$/, () => 'Этого козыря уже нет в комбинации'],
  [/^target card is not a wild card$/, () => 'Выбранная карта — не козырь'],
  [
    /^replacement must be rank (\S+)$/,
    (m) => `Для замены нужна карта достоинства ${m[1]}`,
  ],
  [
    /^replacement must be (\S+) of (\S+) at this position$/,
    (m) => `На это место подходит только ${m[1]} масти «${suitRu(m[2])}»`,
  ],
  [/^wild_side must be/, () => 'Неверная сторона для козыря'],
  [
    /^opening threshold not met - melds returned to hand$/,
    () =>
      'Порог открытия не пройден — выложенные карты возвращены в руку. Выложите комбинации на нужную сумму или просто сбросьте карту',
  ],
  [/^game is not in progress$/, () => 'Игра ещё не началась или уже закончена'],
  [/^no active deal$/, () => 'Сейчас нет активной сдачи'],
  [/^unknown (intent|action)/, () => 'Неизвестное действие'],
]

export function isOpeningThresholdRollback(reason: string | null): boolean {
  return reason === 'opening threshold not met - melds returned to hand'
}

export function translateActionError(reason: string): string {
  for (const [pattern, build] of TRANSLATIONS) {
    const match = reason.match(pattern)
    if (match) return build(match)
  }
  return reason
}
