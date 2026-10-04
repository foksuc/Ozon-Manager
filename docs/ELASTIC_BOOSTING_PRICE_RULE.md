> **Current release context — 04.10.2026:** Historical/date-specific findings in this document are preserved. Current release verification is **256 passed, 1 skipped** with `compileall` PASS. Known Promotions API shutdown risk is documented in `docs/API_RECONCILIATION.md` and `docs/RELEASE_AUDIT.md`.

# Elastic Boosting — Price Rule

## Candidate → Participant (ADD)

Для обычного ручного добавления кандидата приложение использует фактически
возвращённые Ozon поля `price_min_elastic` и `price_max_elastic`. Это не
заменяется фиксированным пределом 18%.

Для каждого товара рассчитывается индивидуальный диапазон скидки от текущей
`Цена`:

```text
min_discount = (Цена - price_min_elastic) / Цена × 100
max_discount = (Цена - price_max_elastic) / Цена × 100
```

ADD разрешён только если рассчитанная новая цена попадает в диапазон: `price_max_elastic ≤ новая цена ≤ price_min_elastic`.

Если Ozon не вернул оба порога либо они противоречат ожидаемому порядку,
добавление блокируется fail-closed. Mutation не выполняется.

### Пример

Для товара:

- Цена = `2700 ₽`;
- `price_min_elastic = 2314 ₽`;
- `price_max_elastic = 1913 ₽`.

Получаем:

- минимальная скидка = `14.30%` → `2314 ₽`;
- максимальная скидка = `29.15%` → `1913 ₽`.

В редакторе ADD эти значения показываются непосредственно в колонках
`Price min elastic` и `Price max elastic` в формате `N% → цена`.

Начальная скидка нового товара автоматически устанавливается на его
индивидуальную минимальную скидку. Ручное изменение скидки разрешается только
в рассчитанном для этого товара диапазоне.

## Participant price UPDATE

Изменение цены уже участвующего товара использует тот же фактически
возвращённый Ozon диапазон `price_min_elastic` / `price_max_elastic`, что и ADD.
Фиксированного приложения-ограничения `1%–18%` для UPDATE_PRICE больше нет.

Запрошенная абсолютная цена проверяется после Fresh Check и повторно
непосредственно перед snapshot/mutation. Если актуальный Ozon диапазон не
позволяет запрошенную цену, mutation блокируется fail-closed.

## Safety

Проверка диапазона выполняется дважды:

1. в UI при расчёте/редактировании пакета;
2. непосредственно перед mutation после Fresh Check по свежему состоянию кандидата.

Таким образом, старый рассчитанный процент не может быть отправлен после
изменения Ozon `price_min_elastic` / `price_max_elastic`.


## Global percentage for Participant UPDATE

The UPDATE dialog supports applying one percentage to all selected participants. The UI first checks that the requested percentage is inside every product's individually calculated interval. In particular, the requested percentage must not be below that product's required minimum discount. The maximum is also checked to keep the resulting price inside the Ozon interval.

Validation is all-or-nothing for the UI plan: one failing product prevents the global percentage from being applied to the package. When validation passes, each product receives its own absolute calculated price derived from its own base price and Elastic boundaries.

Predefined percentages in the UI are convenience choices only. They are not Ozon API limits and do not establish a business maximum/minimum.
