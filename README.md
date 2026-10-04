# Task 1.1 — Draw the architecture MCP

![Архітектура MCP](diagram.png)

Це проєкт архітектури для сценарію: прочитати GitHub issue та локальний код, створити Jira ticket і надіслати повідомлення у Slack. Назви інструментів умовні; реалізація має надавати лише перелічені можливості.

## Host і Clients

Host — IDE або чат-бот із LLM та runtime для orchestration. Host керує чотирма MCP Clients, кожен із яких під’єднаний до одного MCP Server. Зв’язок 1:1 стосується Client ↔ Server: спільний мережевий сервер може обслуговувати Clients різних користувачів.

LLM пропонує tool call; Host перевіряє аргументи, права та approval, а потім виконує дозволений виклик через відповідний Client.

## Мінімальні привілеї

| Server | Read Tools | Write Tools | Human approval |
|---|---|---|---|
| GitHub | `get_issue`, `search_issues` | Немає | Для звичайного читання не потрібен |
| Jira | `search_tickets` — дозволений для пошуку дублікатів | `create_ticket` | Перед створенням тікета |
| Slack | Немає | `send_message` | Перед надсиланням повідомлення |
| FS | `read_file`, `list_directory` | Немає | Для читання дозволених файлів не потрібен |

Ці обмеження застосовуються і до інструментів, і до API scopes, Resources та доступу до каталогів. GitHub дозволяє читання issues лише потрібних репозиторіїв; Jira — пошук і створення у визначеному проєкті; Slack — надсилання у дозволені канали; FS — читання визначених каталогів. Самого приховування зайвих Tools від моделі недостатньо: права перевіряє сервер.

## Транспорт і причини вибору

- **FS — stdio.** Client запускає сервер як дочірній процес на ПК з Host; обмін іде через stdin/stdout без мережевого порту для MCP. За звичайного запуску процес успадковує права користувача Host. Allowlist каталогів і read-only доступ налаштовуються окремо: stdio їх не гарантує. Для цього сценарію FS локальний, бо читає незмонтовані локальні файли; загалом MCP допускає віддалений FS.
- **GitHub — Streamable HTTP через HTTPS.** Issues живуть у GitHub, а командний MCP-сервіс надає спільний керований доступ лише на читання.
- **Jira — Streamable HTTP через HTTPS.** Тікети живуть у Jira; командний MCP-сервіс централізує дозволений проєкт і право створення.
- **Slack — Streamable HTTP через HTTPS.** Повідомлення надсилаються через Slack API; командний MCP-сервіс обмежує доступ дозволеними каналами.

Транспорт позначено на зв’язку **Client ↔ MCP Server**. Зв’язок **MCP Server ↔ SaaS API** використовує HTTPS незалежно від MCP-транспорту. Альтернатива: локальний GitHub MCP Server через stdio, зокрема в контейнері, із запитами до GitHub API через HTTPS.

У специфікації MCP від **2025-03-26** Streamable HTTP замінив старий **HTTP+SSE** із версії 2024-11-05. HTTP+SSE — legacy для сумісності; використання SSE всередині Streamable HTTP залишається можливим.

## Авторизація

Для обраної архітектури команда розгортає й адмініструє мережеві MCP-сервіси. Client авторизується на MCP endpoint через OAuth. MCP-сервіс окремо авторизується у відповідному SaaS API через підтримуваний ним OAuth або API token із мінімальними scopes. Токен MCP endpoint і токен SaaS API — різні облікові дані; вони не передаються автоматично між цими рівнями.

Client зберігає свої токени у захищеному сховищі Host; сервер — свої токени в secret store. Секрети можна інжектувати в процес через env. Вони не потрапляють у Git, Prompts або контекст LLM. OAuth scopes обмежують можливості, але не замінюють підтвердження конкретної write-операції.

## Хто керує примітивами

| Примітив | Хто ініціює використання | Приклад |
|---|---|---|
| Tools | Модель: model-controlled; виконання контролює Host | LLM пропонує `get_issue` або `read_file` |
| Resources | Застосунок: application-controlled | Host додає дозволений файл або вміст issue у контекст |
| Prompts | Користувач: user-controlled | Користувач запускає шаблон «Створи Jira-тікет з GitHub issue» |

`read_file` і Resource з файлом можуть надавати однаковий вміст, але мають різні механізми ініціювання. Read-only Tool залишається Tool. Resources не дають права змінювати дані. Jira і Slack у цьому проєкті не публікують Resources; Prompt сценарію публікує Jira Server.

## Сценарій і підтвердження

1. Користувач явно запускає Jira Prompt і вказує GitHub issue.
2. Host отримує issue та, за потреби, читає дозволені локальні файли. Отриманий текст є даними, а не новими повноваженнями чи інструкціями для Host.
3. Агент перевіряє дублікати через `search_tickets` і готує чернетку.
4. Host показує проєкт та поля тікета. Після підтвердження виконується `create_ticket`.
5. Агент готує повідомлення з посиланням на створений тікет. Host показує канал і текст; після окремого підтвердження виконується `send_message`.

Approval — політика цієї архітектури. Запуск Prompt не є автоматичним дозволом на всі наступні write-операції.

## Джерела

- [MCP Transports, 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
- [MCP Server primitives, 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/server/index)
- [MCP Authorization, 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization)

# Task 2.1 - Analyse a tool schema

У поганій схемі назва get_data та опис gets data не пояснюють призначення інструмента, тому LLM складно визначити, коли обирати його серед інших tools. Поле input без опису не уточнює, що передавати, а відсутність required дозволяє виклик із {}, який може спричинити помилку виконання. У покращеній схемі назва search_codebase та опис призначення й результатів допомагають моделі обрати інструмент для пошуку коду, який виконує сам tool. Описи аргументів, приклади, обов’язковий pattern і тип integer для max_results зменшують неоднозначність та ризик передати число рядком, як "5", підвищуючи ймовірність коректного виклику з першої спроби й зменшуючи кількість повторних спроб. Фільтр file_extension звужує пошук, а max_results обмежує кількість збігів і витрати токенів на результати, якщо сервер застосовує цей параметр та значення 20 за замовчуванням.

# Task 1.3 — Choose a framework 

| Сценарій | Вибір | Обґрунтування |
|---|---|---|
| **A — чат-бот підтримки** | **LangGraph** | Дозволяє явно описати розгалуження: пошук у документації → відповідь або передача людині. Збереження стану й human-in-the-loop допомагають продовжити роботу після втручання оператора. ([GitHub][1]) |
| **B — щотижневий звіт** | **bare MCP** | Для фіксованої послідовності «зібрати дані → викликати LLM для підсумку → надіслати у Slack» достатньо простого скрипта з MCP-інструментами. Розклад, порядок кроків і обробку помилок реалізує застосунок: MCP забезпечує доступ до інструментів, а оркестрацією керує Host. ([GitHub][2]) |
| **C — код → тести → виправлення** | **LangGraph** | Граф дозволяє побудувати цикл із переходом за результатами тестів і лічильником повторів у стані. Перевірка лічильника в коді гарантує завершення після максимум трьох повторів, незалежно від рішення LLM. ([LangChain Reference][3]) |
| **D — Researcher → Analyst → Writer** | **CrewAI** | Підходить для команди агентів із чіткими ролями, цілями та окремими завданнями. Послідовний процес передає результати дослідження аналітику, а результати аналізу — автору звіту. ([CrewAI][4]) |

[1]: https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/overview.mdx?utm_source=chatgpt.com "docs/src/oss/langgraph/overview.mdx at main · langchain-ai/docs"

[2]: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2025-11-25/architecture/index.mdx?utm_source=chatgpt.com "modelcontextprotocol/docs/specification/2025-11-25/architecture/index.mdx at main · modelcontextprotocol/modelcontextprotocol"

[3]: https://reference.langchain.com/python/langgraph/overview?utm_source=chatgpt.com "LangGraph - Python API Reference"

[4]: https://docs.crewai.com/core-concepts/Agents?utm_source=chatgpt.com "Introduction"



# Task 2.1 — MCP server

Сервер: [mcp_server.py](mcp_server.py) (FastMCP, transport stdio) з інструментами `read_file(path) -> str` і `list_directory(path) -> list[str]`. Схеми з описами генеруються з docstring та `Field(description=...)`. Неіснуючий шлях повертає повідомлення `ПОМИЛКА: ...` замість винятку.

Запуск локально (без VM):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mcp dev mcp_server.py                      # інспектор (потрібен node/npx)
OLLAMA_MODEL=qwen2.5:7b python lab2.py   # агент через локальну Ollama
```

## Промпти та ручні правки

Використаний AI-інструмент: Claude Code (чат у IDE). Промпти:

1. Текст завдання Task 2.1 (MCP-сервер з `read_file` і `list_directory`, stdio, JSON-схеми з `description`, обробка помилок) і прохання переробити наявні скрипти під мої умови: без VM Vagrant, з локальною Ollama (`mistral:7b-instruct-q4_K_M`).
2. Повідомлення про помилки під час запуску: `mcp dev` просив `typer`; `lab2.py` падав з `ExceptionGroup`; агент не вкладався в таймаут. Кожного разу я вставляв вивід термінала й просив виправити.
3. Прохання перейти на `qwen2.5:7b`.

Що довелося виправляти за підсумком запусків:
- Вихідний сервер мав інші інструменти (`search_documents`, `file_read`) і зламаний відступ у `call_tool_handler`; переписано на FastMCP з `read_file` та `list_directory`.
- `pip install mcp` ставить 2.x, де `FastMCP` перейменовано на `MCPServer`; зафіксовано `mcp<2`.
- `mcp dev` вимагає `typer`; залежність змінено на `mcp[cli]<2`.
- Прибрано шлях `/home/vagrant/...` та IP VM: клієнт використовує `sys.executable` і шлях відносно файлу, Ollama - `localhost:11434`.
- `mistral:7b-instruct-q4_K_M` не підтримує tools в Ollama (помилка 400 `does not support tools`); замінено на `qwen2.5:7b`.
- Модель частково працює на CPU, тому таймаут зроблено налаштовуваним (`AGENT_TIMEOUT`, 1200 с), а агент читає короткий `requirements.txt` замість README.md.
- На кроці 2 модель написала "я перечитав файл", хоча лише згадала вже прочитаний; це обмеження 7B-моделі, код тут ні до чого.

# Task 2.2 — ReAct-агент з контрольною точкою

Агент: [agent.py](agent.py). Підключається до MCP-сервера з Task 2.1 ([mcp_server.py](mcp_server.py): `read_file`, `list_directory`) через stdio, будує ReAct-граф LangGraph (`create_react_agent`) із чекпоінтером `AsyncSqliteSaver` (файл `checkpoints.db`, не потрапляє в Git). `MemorySaver` не підходить для перезапуску процесу: він живе лише в пам'яті. Модель — `qwen2.5:7b` через Ollama.

Логіка запуску за `thread_id` (`THREAD_ID`, за замовчуванням `task22_thread`):
- стану немає: новий запуск із завданням;
- стан незавершений (`state.next` не порожній): відновлення з `None` на вході без повторного запиту;
- стан завершений: виводить збережену відповідь і `[VERIFIED]`.

Захисні межі (AgentOps), усі налаштовуються змінними середовища:
- `RECURSION_LIMIT` (10): ліміт кроків графа, при перевищенні `GraphRecursionError` і код виходу 2;
- `LLM_TIMEOUT` (120 с): timeout запиту до Ollama, `max_retries=0`;
- рядок `[SYSTEM] model=... url=... temperature=... timeout=... recursion_limit=... thread_id=...` фіксує параметри прогону для відтворюваності.

Підрахунок рядків робить код, а не LLM: після завершення `[VERIFIED]` береться з результату `read_file` у збереженому стані (`len(text.splitlines())`).

Запуск:
```bash
pip install -r requirements.txt
THREAD_ID=hw12_final STEP_DELAY=15 python -u agent.py 2>&1 | tee run1.log   # Ctrl+C у паузі після першого [TOOL CALL]
THREAD_ID=hw12_final python -u agent.py 2>&1 | tee -ia run2.log             # той самий thread_id: відновлення
```
`-u` потрібен, щоб вивід не буферизувався через `tee`.

## Журнал виконання

Повні логи: [run1.log](run1.log), [run2.log](run2.log). Нижче скорочено (прибрано рядки `INFO` від MCP та попередження про deprecation `create_react_agent`).

Прогін 1: Ctrl+C у паузі після рішення моделі викликати `list_directory`, до виконання інструмента:
```
[SYSTEM] model=qwen2.5:7b url=http://localhost:11434/v1 temperature=0.0 timeout=120.0s recursion_limit=10 thread_id=hw12_final
[SYSTEM] thread_id='hw12_final': новий запуск.
[USER] Find all .py files in the current directory, read the first file found, and report how many lines it contains
[TOOL CALL] list_directory({'path': '.'})
^C
```

Прогін 2: той самий `thread_id`. Стан підхоплено з SQLite (2 повідомлення, наступний вузол `tools`), завдання не надсилається повторно, `list_directory` виконується вже після відновлення. Я ще раз перервав (Ctrl+C) після результату, тож стан став «3 повідомлення, наступний вузол `agent`». Фінальне відновлення:
```
[SYSTEM] thread_id='hw12_final': знайдено незавершений стан (3 повідомлень, наступний вузол: ('agent',)). ВІДНОВЛЕННЯ без повторного запиту.
[TOOL CALL] read_file({'path': 'crewai_agent.py'})
[MCP SERVER LOG] read_file(path='crewai_agent.py')
[TOOL RESULT] read_file: import os
from crewai import Agent, Task, Crew, Process, LLM
...
[AI] The file "crewai_agent.py" contains 127 lines.
[VERIFIED] crewai_agent.py contains 65 lines (підраховано кодом)
```

Разом 2 виклики інструментів: `list_directory({'path': '.'})` і `read_file({'path': 'crewai_agent.py'})`. Жодне переривання не повторювало вже виконані кроки.

## Промпти та ручні правки

Промпти до AI-асистента (Claude Code): текст завдання Task 2.2 (ReAct на LangGraph, збереження стану, відновлення після Ctrl+C), а потім список зауважень з рев'ю: підрахунок рядків, назва `mcp_server.py`, `recursion_limit`, timeout, модель і URL у лозі.

Що довелося виправляти:
- `MemorySaver` не переживає перезапуск процесу, тому використано `AsyncSqliteSaver` (`langgraph-checkpoint-sqlite`, `aiosqlite`).
- Результат MCP-інструмента приходить списком текстових блоків; для виводу їх склеєно в один рядок.
- Без системного промпта модель повторювала `list_directory` і переказувала файл; додано `SYSTEM_PROMPT`.
- Через `| tee` вивід буферизувався, тому Ctrl+C було важко влучити в паузу; додано `python -u`, `STEP_DELAY` і `tee -i`.
- **Підрахунок рядків.** 7B-модель рахує неправильно і нестабільно: у різних прогонах відповіді були 53 і 127, а справжнє значення 65 (`wc -l`). Навіть із забороною в промпті модель все одно називає число. Тому обчислення винесено в код (`[VERIFIED]`), а відповідь LLM не вважається джерелом істини. Це обмеження моделі, а не механізму чекпоінтів чи MCP.
- «Перший файл»: `list_directory` повертає `sorted(...)`, тож порядок детермінований (`crewai_agent.py` — перший `.py`). Сортування чутливе до регістру.
- `create_react_agent` позначено deprecated у LangGraph 1.0 (замінник `langchain.agents.create_agent`); міграцію свідомо відкладено.
