import os
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters

# 1. Налаштування локальної моделі Ollama llama3.1:8b
# Переконайтеся, що Ollama запущена локально (зазвичай на порту 11434)
local_llm = LLM(
    model="ollama/llama3.1:8b",
    base_url="http://192.168.88.188:11434"
)

# 2. Параметри локального MCP-сервера 
mcp_config = StdioServerParameters(
    command="python",
    args=["/home/vagrant/labs/mcp_server_lab1.py"],
    env={**os.environ}
)

def main():
    print("--- Ініціалізація MCP Адаптера ---")
    mcp_adapter = MCPServerAdapter(mcp_config)

    # Використовуємо менеджер контексту для роботи з інструментами
    with mcp_adapter:
        mcp_tools = mcp_adapter.tools
        print(f"Виявлено інструментів від MCP сервера: {len(mcp_tools)}")

        # 3. Створення Агента з підтримкою локальної Ollama
        researcher = Agent(
            role="Дослідник даних",
            goal="Використовувати підключений MCP-сервер для аналізу інформації",
            backstory="Експерт з інтеграції та збору даних через універсальні протоколи контексту.",
            tools=mcp_tools,
            llm=local_llm,  # ПЕРЕДАЄМО НАШУ ЛОКАЛЬНУ МОДЕЛЬ СЮДИ
            verbose=True,
            memory=False
        )

        # 4. Створення Завдання (Task)
        research_task = Task(
            description=(
                "Дослідити доступні ресурси за допомогою інструментів MCP-сервера. "
                "Зібрати фінальний аналітичний звіт та структурувати його українською мовою."
            ),
            expected_output="Повний текстовий звіт на основі даних, отриманих з MCP інструментів.",
            agent=researcher
        )

        # 5. Формування Команди (Crew)
        crew = Crew(
            agents=[researcher],
            tasks=[research_task],
            process=Process.sequential,
            verbose=True
        )

        print(f"--- Запуск CrewAI (модель: llama3.1:8b) ---")
        result = crew.kickoff()
        
        print("\n--- Результат роботи агента: ---")
        print(result)

if __name__ == "__main__":
    main()
