# Bazaar Analysis

Инструменты для поиска прибыльных крафтов в Hypixel SkyBlock Bazaar. Приложение забирает данные с официального API, объединяет их с описаниями рецептов и оценивает потенциальную прибыль, окупаемость и популярность крафтов.

## Установка

Проект не требует сторонних зависимостей. Нужен Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .  # необязательно, можно запускать напрямую
```

## Использование

1. Скачайте список рецептов с помощью утилиты (по умолчанию он фильтруется по товарам, представленным на базаре):

   ```bash
   python -m bazaar_analysis.cli fetch-recipes --output recipes.json
   ```

   Если у вас есть API-ключ Hypixel, укажите его через `--api-key` или переменную окружения `HYPIXEL_API_KEY`. Для получения полного списка рецептов добавьте `--include-all`.

2. Либо подготовьте JSON-файл вручную (см. `data/sample_recipes.json`).
3. Запустите анализ:

```bash
python -m bazaar_analysis.cli analyze recipes.json --top 10 --min-profit 10000
```

По умолчанию утилита обращается к Hypixel API. Чтобы не превышать лимиты, можно сохранять снимок в файл и передавать его через `--bazaar-cache`.

```bash
python -m bazaar_analysis.cli analyze recipes.json --bazaar-cache snapshot.json --dump-results flips.json
```

### Формат рецептов

```json
{
  "recipes": [
    {
      "product_id": "ENCHANTED_SUGAR",
      "output_amount": 1,
      "ingredients": [
        {"product_id": "SUGAR_CANE", "amount": 160}
      ]
    }
  ]
}
```

## Тесты

```bash
pytest
```
