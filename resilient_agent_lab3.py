import asyncio 
import random 
from tenacity import retry, wait_exponential, retry_if_exception_type, stop_after_attempt 
from langchain_core.tools import BaseTool 

class ToolExecutionError(Exception): 
    """Спеціальне виключення для фіксації помилок виконання MCP-інструменту""" 
    pass 

# Mock-клас первинного інструменту із нестабільною роботою 
class UnstablePrimaryTool(BaseTool): 
    name: str = "primary_database_query" 
    description: str = "Первинний інструмент доступу до бази даних." 

    def _run(self, query: str) -> str:
        """Синхронна реалізація обов'язкова для LangChain BaseTool"""
        raise NotImplementedError("Цей інструмент підтримує лише асинхронне виконання через _arun")

    async def _arun(self, query: str) -> str: 
        # Імітація 70% ймовірності мережевої помилки 
        if random.random() < 0.7: 
            print(" [PRIMARY TOOL] Збій мережі! Помилка з'єднання з DB.") 
            raise ToolExecutionError("Connection timeout to primary DB.") 
        print(" [PRIMARY TOOL] Запит успішно виконано!") 
        return f"Результати первинної БД для: '{query}'" 

# Mock-клас резервного інструменту (Fallback) 
class ReliableFallbackTool(BaseTool): 
    name: str = "fallback_cache_query" 
    description: str = "Резервний інструмент читання з локального кешу." 

    def _run(self, query: str) -> str:
        """Синхронна реалізація обов'язкова для LangChain BaseTool"""
        raise NotImplementedError("Цей інструмент підтримує лише асинхронне виконання через _arun")

    async def _arun(self, query: str) -> str: 
        print(" [FALLBACK TOOL] Отримання даних із резервного локального кешу.") 
        return f"Кешовані дані для: '{query}'" 

# Клас-обгортка для забезпечення відмовостійкості та ідемпотентності 
class ResilientToolExecutor: 
    def __init__(self, primary_tool: BaseTool, fallback_tool: BaseTool = None): 
        self.primary_tool = primary_tool 
        self.fallback_tool = fallback_tool 

    # Декоратор Tenacity: Exponential Backoff (1s -> 2s -> 4s ..., max 10s, max 3 спроби) 
    @retry( 
        wait=wait_exponential(multiplier=1, min=1, max=10), 
        stop=stop_after_attempt(3), 
        retry=retry_if_exception_type(ToolExecutionError), 
        reraise=True 
    ) 
    async def _execute_with_retry(self, tool: BaseTool, args: dict): 
        print(f" [RETRY RUNNER] Спроба виклику {tool.name}...") 
        # Зверніть увагу: метод arun приймає аргументи як іменовані параметри (**args) або через словник, 
        # але для BaseTool краще розпаковувати або передавати коректно.
        return await tool.arun(args) 

    async def execute(self, args: dict) -> str: 
        """Виконання інструменту з патерном Retry -> Fallback""" 
        try: 
            # Спроба виконати первинний інструмент з retries 
            return await self._execute_with_retry(self.primary_tool, args) 
        except ToolExecutionError as e: 
            print(f" [WARNING] Первинний інструмент відмовив після 3 спроб: {e}") 
            if self.fallback_tool: 
                print(" [CIRCUIT BREAKER] Перемикання на Fallback інструмент...") 
                # Виконання резервного інструменту 
                return await self.fallback_tool.arun(args) 
            raise RuntimeError("Всі доступні інструменти відмовили у виконанні.") 

async def main(): 
    primary = UnstablePrimaryTool() 
    fallback = ReliableFallbackTool() 
    executor = ResilientToolExecutor(primary_tool=primary, fallback_tool=fallback) 
    print("--- Тест 1: Виконання запиту з підтримкою Retry та Fallback ---") 
    result = await executor.execute({"query": "SELECT * FROM users;"}) 
    print("Підсумковий результат операції:", result) 

if __name__ == "__main__": 
    asyncio.run(main())
