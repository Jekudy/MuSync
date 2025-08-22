# Настройка GitHub репозитория для MuSync

## Текущее состояние

✅ Git репозиторий инициализирован  
✅ Первый коммит создан  
✅ .gitignore настроен  
✅ Git конфигурация настроена  

## Следующие шаги

### 1. Создание репозитория на GitHub

1. Перейдите на [GitHub](https://github.com)
2. Нажмите "New repository"
3. Название: `MuSync`
4. Описание: `MuSync - Music synchronization service between Spotify and Yandex Music`
5. Выберите "Public"
6. **НЕ** инициализируйте с README (у нас уже есть)
7. Нажмите "Create repository"

### 2. Подключение локального репозитория к GitHub

После создания репозитория на GitHub, выполните команды:

```bash
# Добавление удаленного репозитория
git remote add origin https://github.com/eekudryavtsev/MuSync.git

# Переименование основной ветки в main (если нужно)
git branch -M main

# Отправка кода на GitHub
git push -u origin main
```

### 3. Настройка защиты веток (опционально)

В настройках репозитория на GitHub:

1. Settings → Branches
2. Add rule для `main`
3. Включить:
   - Require pull request reviews
   - Require status checks to pass
   - Include administrators

### 4. Настройка GitHub Actions (опционально)

Создайте `.github/workflows/ci.yml` для автоматических тестов:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    - name: Run tests
      run: |
        python -m pytest
```

### 5. Настройка Issues и Projects

1. Создайте шаблоны для Issues
2. Настройте Project board для отслеживания задач
3. Добавьте labels для категоризации

## Проверка настройки

После выполнения всех шагов:

```bash
# Проверка удаленного репозитория
git remote -v

# Проверка статуса
git status

# Проверка веток
git branch -a
```

## Полезные команды для работы

```bash
# Создание новой ветки
git checkout -b feature/new-feature

# Отправка изменений
git add .
git commit -m "Описание изменений"
git push origin feature/new-feature

# Слияние изменений из main
git checkout main
git pull origin main
git checkout feature/new-feature
git merge main
```

## Рекомендации

1. **Коммиты**: Делайте частые, атомарные коммиты
2. **Сообщения**: Используйте понятные сообщения на русском языке
3. **Ветки**: Создавайте отдельные ветки для каждой функции
4. **Pull Requests**: Всегда создавайте PR для слияния в main
5. **Тесты**: Добавляйте тесты для новой функциональности
