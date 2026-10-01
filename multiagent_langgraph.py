import asyncio
from typing import TypedDict, Literal
#from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END


# Опис стану мультиагентної системи
class AgentState(TypedDict):
    task: str
    research_data: str
    final_draft: str
    next_node: str


# Ініціалізація локальної LLM
llm = ChatOpenAI(
                        model="llama3.1:8b",
                        base_url="http://192.168.88.188:11434/v1",
                        api_key="ollama",
                        temperature=0.0
                    )


# 1. Supervisor Node (LLM-driven Router)
async def supervisor_node(state: AgentState):
    print("\n[SUPERVISOR] Аналіз стану та вибір наступного агента...")
    if not state.get("research_data"):
        return {"next_node": "researcher"}
    elif not state.get("final_draft"):
        return {"next_node": "writer"}
    return {"next_node": END}


# 2. Researcher Node
async def researcher_node(state: AgentState):
    print("[RESEARCHER] Виконання збору інформації...")
    prompt = f"Виконай дослідження за задачею: {state['task']}. Надай 2-3 коротких факти."
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {"research_data": response.content}


# 3. Writer Node
async def writer_node(state: AgentState):
    print("[WRITER] Формування підсумкового звіту...")
    prompt = f"На основі даних: {state['research_data']}, напиши короткий підсумковий звіт."
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {"final_draft": response.content}


# Побудова графа
workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("researcher", researcher_node)
workflow.add_node("writer", writer_node)


workflow.set_entry_point("supervisor")


# Додавання умовних ребер на основі рішення Supervisor
workflow.add_conditional_edges(
    "supervisor",
    lambda state: state["next_node"],
    {
        "researcher": "researcher",
        "writer": "writer",
        END: END
    }
)


workflow.add_edge("researcher", "supervisor")
workflow.add_edge("writer", "supervisor")


app = workflow.compile()


async def main():
    initial_state = {
        "task": "Проаналізувати переваги використання MCP у порівнянні з REST API",
        "research_data": "",
        "final_draft": "",
        "next_node": ""
    }
    final_output = await app.ainvoke(initial_state)
    print("\n================ РЕЗУЛЬТАТ РОБОТИ МУЛЬТИАГЕНТА ================")
    print(final_output["final_draft"])


if __name__ == "__main__":
    asyncio.run(main())
