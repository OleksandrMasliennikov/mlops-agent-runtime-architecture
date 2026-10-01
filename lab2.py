import asyncio
import sys
import traceback
import langchain

from mcp import StdioServerParameters, stdio_client, ClientSession
from langchain_mcp_adapters.tools import load_mcp_tools
# Використовуємо універсальний ChatOpenAI, адаптований під API Ollama
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

# Конфігурація параметрів запуску MCP-сервера через stdio
server_params = StdioServerParameters(
    command="python",
    args=["/home/vagrant/labs/mcp_server_lab1.py"]
)


async def main():
    print("[SYSTEM] Запуск клієнта LangChain...", file=sys.stderr)
    try:
        async with asyncio.timeout(30):
            # 1. Ініціалізація з'єднання з MCP-сервером
            async with stdio_client(server_params) as (read_stream, write_stream):
                print("[SYSTEM] stdio_client з'єднання встановлено", file=sys.stderr)
                async with ClientSession(read_stream, write_stream) as session:
                    print("[SYSTEM] ClientSession створено, викликаю initialize()", file=sys.stderr)
                    await session.initialize()
                    print("[SYSTEM] initialize() успішно завершено", file=sys.stderr)

                    # Конвертація MCP-інструментів у формат LangChain BaseTool
                    tools = await load_mcp_tools(session)
                    print(f"[SYSTEM] Успішно завантажено {len(tools)} інструмент(ів) з MCP-сервера.")

                    # 2. Налаштування моделі Ollama через сумісний OpenAI API клієнт
                    llm = ChatOpenAI(
                        model="llama3.1:8b",
                        base_url="http://192.168.88.188:11434/v1",
                        api_key="ollama",
                        temperature=0.0
                    )

                    # 3. Налаштування асинхронного чекпоінтера стану розмови (в оперативній пам'яті)
                    checkpointer = MemorySaver()

                    # 4. Створення ReAct-агента (автоматично будує StateGraph)
                    agent = create_react_agent(
                        model=llm,
                        tools=tools,
                        checkpointer=checkpointer
                    )

                    # Конфігурація сесії з унікальним ідентифікатором потоку (thread_id)
                    config = {"configurable": {"thread_id": "student_session_101"}}

                    # Перший крок розмови: запит на використання інструменту
                    print("\n--- Крок 1: Пошук документів ---")
                    inputs = {"messages": [("user", "Знайди документи за запитом 'системний аудит' та прочитай їх вміст.")]}

                    print("[SYSTEM] Надсилання запиту до Ollama (очікуйте на повну відповідь)...", file=sys.stderr)

                    result_1 = await agent.ainvoke(inputs, config)

                    print("\n[ХІД РОЗМОВИ З ПАМ'ЯТІ АГЕНТА]:")
                    for msg in result_1["messages"]:
                        role = msg.__class__.__name__.replace("Message", "")
                        print(f"[{role}]: {msg.content}")
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            print(f"   -> Виклик інструменту: {msg.tool_calls}")

                    # Другий крок розмови: перевірка пам'яті за тим самим thread_id
                    print("\n\n--- Крок 2: Перевірка контексту пам'яті ---")
                    inputs_2 = {"messages": [("user", "Який запит ми щойно шукали у базі знань?")]}

                    result_2 = await agent.ainvoke(inputs_2, config)
                    print("Відповідь з пам'яті агента:", result_2["messages"][-1].content)

    except TimeoutError:
        print("[ERROR] Таймаут 30с: щось зависло (з'єднання з сервером, LLM або tool call).", file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("[ERROR] Виникла помилка:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())