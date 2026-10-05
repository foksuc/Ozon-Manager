# Auto-Add — все акции Ozon — UI V1

Дата: 2026-10-05

## Цель

Переработать раздел «Автодобавление Ozon» так, чтобы он не был визуально и навигационно привязан только к акции `1977747` («Эластичный бустинг. Без ограничения срока действия»), при этом не менять существующую transport/mutation-логику Auto-Add.

## Источник API-контракта

Использован локальный `Ozon API Reference` проекта.

Подтверждено:

- `GET /v1/actions` возвращает `auto_add_dates` внутри каждой акции;
- Auto-Add list/delete работают с точными `action_id` + `auto_add_date`;
- `auto_add_date` берётся из `result.auto_add_dates` ответа `/v1/actions`;
- текущий UI переиспользует уже существующие adapter/service методы, не создавая новый mutation path.

## UI/UX изменения

1. На основном экране кнопка теперь называется только `Автодобавление Ozon` — без количества товаров.
2. Текст кнопки центрирован.
3. Кнопка открывает единое окно Auto-Add.
4. В первом состоянии окна показываются все акции, для которых Ozon реально вернул непустой `auto_add_dates`.
5. Кнопки акций расположены в две колонки.
6. Товары не загружаются сразу для всех акций: запрос выполняется только после выбора конкретной акции. Это предотвращает fan-out запросов.
7. Если у акции несколько `auto_add_dates`, пользователь выбирает точную дату через select.
8. После выбора акции используется та же таблица Auto-Add и тот же пороговый фильтр удаления, которые существовали ранее.
9. План удаления сохраняет фактические `action_id` и `auto_add_date` выбранной акции.
10. После подтверждённого удаления кэш выбранной акции/даты инвалидируется, а окно возвращается к выбранной акции с обновлёнными данными.

## Что не менялось

Побайтово сохранены:

- `app/adapters/ozon.py`
- `app/adapters/ozon_sdk.py`
- `app/services/auto_add.py`
- `app/services/membership.py`
- `app/services/workflow.py`
- `app/services/rollback.py`
- `app/services/price_engine.py`
- `app/repositories/sqlite.py`
- `app/domain/models.py`
- `app/domain/validation.py`

То есть не изменялись:

- API endpoints;
- payload schemas;
- Fresh Check;
- snapshot-before-mutation;
- confirmation;
- deletion execution;
- reconciliation;
- rollback;
- history semantics.

## Безопасность

Auto-Add hub меняет только выбор источника (`action_id`, `auto_add_date`). Само удаление по-прежнему проходит через `AutoAddDeleteService` и отдельный confirmation dialog.

## Проверки

Добавлен `tests/test_auto_add_all_promotions_ui.py`, который фиксирует:

- отсутствие количества на основной кнопке;
- центрирование кнопки;
- discovery всех акций по `auto_add_dates`;
- раскладку акций в 2 колонки;
- отсутствие `FIXED_ACTION_ID` внутри Auto-Add hub;
- передачу выбранных `action_id` и `auto_add_date` в план удаления;
- повторное использование существующего `AutoAddDeleteService`;
- очистку multi-action UI cache при принудительном обновлении.
