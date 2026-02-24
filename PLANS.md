# Portfolio Tracker — Plans

## 1. Trade Republic Integration

### 1a. Manual CSV Import (приоритет — сделать первым)
Trade Republic позволяет экспортировать историю транзакций как CSV из приложения/сайта. Написать `scripts/import_tr.py` по аналогии с `import_revolut_csv.py`.

- Скачать пример CSV из TR и изучить формат
- Парсить: покупки, продажи, дивиденды, Sparplan-покупки, комиссии
- Создавать portfolio + holdings + transactions + cash_transactions
- Поддержать идемпотентный ре-импорт (не дублировать транзакции)
- Команда: `pt import tr <file.csv>`

### 1b. Автоматический sync через pytr (опционально, после 1a)
[pytr](https://github.com/pytr-org/pytr) — неофициальная Python-библиотека для приватного WebSocket API Trade Republic.

Возможности: получение портфеля, экспорт транзакций, скачивание PDF-документов.

Подводные камни:
- **Приватный API** — может сломаться без предупреждения при обновлении TR
- **Авторизация**: web login требует 4-значный код каждую сессию; app login разлогинивает из мобильного приложения
- **Нестабильность** — несколько форков из-за заброшенности оригинала
- **Нет гарантий** — не аффилирован с Trade Republic

Решение: использовать pytr опционально, как fallback для `pt sync tr`. Основной путь — ручной CSV-импорт.

---

## 2. Vorabpauschale Calculator

Vorabpauschale — ежегодный налог на нереализованную прибыль accumulating-фондов в Германии. Все 5 ETF в Portfolio A — accumulating, поэтому это актуально.

Формула:
```
Basisertrag = Fondswert_01.01 × Basiszins × 0.7
Vorabpauschale = min(Basisertrag, фактический_прирост_за_год)
Teilfreistellung = 30% для Aktienfonds (>51% equity)
Steuerpflichtiger_Betrag = Vorabpauschale × (1 - Teilfreistellung)
Steuer = Steuerpflichtiger_Betrag × 26.375% (Abgeltungssteuer + Soli)
```

- Basiszins публикуется Bundesbank каждый январь
- Нужно хранить значения Fondswert на 01.01 каждого года
- Teilfreistellung зависит от типа фонда (30% equity, 15% mixed, 0% bond)
- Вычитается из Freistellungsauftrag
- Команда: `pt tax vorabpauschale <portfolio_id> --year 2026`

---

## 3. Migration Workflow (Revolut → Trade Republic)

Пошаговый guided workflow для миграции:

```
pt migrate plan 1 --target-portfolio 2
```

1. Показать текущий Revolut-портфель и кэш
2. Рассчитать налог на продажу всех позиций (Abgeltungssteuer, с учётом Freistellungsauftrag)
3. Показать сумму после продажи и налогов
4. Показать целевое распределение в TR по Portfolio A
5. Рассчитать конкретные покупки (количество × цена) для каждого ETF
6. Показать итоговый план: что продать → сколько получишь → что купить

---

## 4. Sparplan (DCA) Tracking

Monthly Sparplan — автоматические покупки в Trade Republic.

- Таблица `sparplan` в БД: portfolio_id, holding_id, amount_eur, frequency (monthly/biweekly), active
- `pt sparplan set 2 VWCE 300` — установить €300/мес на VWCE
- `pt sparplan list 2` — показать все активные Sparpläne
- `pt sparplan simulate 2 --months 12` — симуляция: как будет выглядеть портфель через N месяцев
- Dashboard: секция с прогрессом DCA

---

## 5. Performance History

Сейчас есть только snapshot текущего состояния. Нужна история.

- Ежедневный snapshot portfolio value в таблицу `portfolio_snapshots` (date, portfolio_id, holdings_value, cash_balance, total_value)
- Time-weighted return (TWR) — корректный расчёт доходности с учётом cash flows
- `pt stats performance 1 --period 1y` — показать доходность за период
- Dashboard: график стоимости портфеля во времени
- Можно автоматизировать через `pt snapshot` запускаемый по cron / schedule

---

## 6. Multi-Portfolio Support

Во время миграции будут одновременно существовать 2 портфеля (Revolut + TR). Уже поддерживается на уровне БД, но нужно:

- `pt portfolio compare 1 2` — сравнение двух портфелей
- `pt stats summary --all` — общая статистика по всем портфелям
- Dashboard: переключатель между портфелями + combined view
- Общий cash balance / P&L across all portfolios

---

## 7. Alerts & Notifications

- Девиация от таргета превышает порог → напоминание о ребалансировке
- P&L достиг определённой суммы
- Freistellungsauftrag скоро исчерпан
- Дивиденд получен
- Реализация: `pt alerts check` (по cron) + вывод в консоль или email/Telegram

---

## 8. Steuererklärung Export

Экспорт данных для Anlage KAP (приложение к налоговой декларации):

- Сумма дивидендов за год
- Реализованная прибыль/убыток
- Уплаченная Vorabpauschale
- Использованный Freistellungsauftrag
- Формат: CSV или PDF-отчёт
- `pt tax report --year 2026`

---

## Приоритеты

| # | Задача | Сложность | Ценность |
|---|--------|-----------|----------|
| 1 | TR CSV import | Средняя | Высокая — без этого нет данных |
| 2 | Vorabpauschale | Средняя | Высокая — прямо влияет на налоги |
| 3 | Migration workflow | Низкая | Высокая — нужно прямо сейчас |
| 4 | Performance history | Средняя | Средняя — приятно, но не срочно |
| 5 | Sparplan tracking | Низкая | Средняя — после настройки DCA в TR |
| 6 | Multi-portfolio | Низкая | Средняя — частично уже работает |
| 7 | pytr автосинк | Высокая | Низкая — приватный API, нестабильно |
| 8 | Alerts | Средняя | Низкая — nice to have |
| 9 | Steuererklärung | Средняя | Низкая — раз в год |
