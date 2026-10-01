import asyncio
import os
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
import mcp.types as types

# 1. Ініціалізація екземпляра MCP-сервера
server = Server("enterprise-tools-server")

# =====================================================================
# 2. ОПРЕДЕЛЕННЯ ФУНКЦІЙ-ОБРОБНИКІВ ЧЕРЕЗ ДЕКОРАТОРИ
#    (декоратори самі загортають return у правильний тип результату,
#     тому НЕ треба вручну реєструвати server.request_handlers[...])
# =====================================================================

# --- ІНСТРУМЕНТИ (TOOLS) ---
@server.list_tools()
async def list_tools_handler() -> list[types.Tool]:
    print("\n[MCP SERVER LOG] Отримано запит на список інструментів (list_tools)!", file=sys.stderr)
    return [
        types.Tool(
            name="search_documents",
            description="Виконує семантичний пошук у локальній базі знань.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Пошуковий запит"},
                    "limit": {"type": "integer", "default": 5, "description": "Кількість результатів"}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="file_read",
            description="Зчитує текстовий вміст файлу за вказаним відносним шляхом.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Відносний шлях до файлу"}
                },
                "required": ["path"]
            }
        )
    ]


@server.call_tool()
async def call_tool_handler(name: str, arguments: dict | None) -> list[types.TextContent]:
    print(f"\n[MCP SERVER LOG] Модель викликає інструмент '{name}' з аргументами: {arguments}", file=sys.stderr)

    if not arguments:
        arguments = {}

        if name == "search_documents":
          query = arguments.get("query")

          # Безпечно конвертуємо в int, навіть якщо Ollama надіслала рядок "5" або "10"
          raw_limit = arguments.get("limit", 5)
        try:
            limit = int(raw_limit)
        except (ValueError, TypeError):
            limit = 5


    elif name == "file_read":
        file_path = arguments.get("path")
        if not file_path or not os.path.exists(file_path):
            return [types.TextContent(type="text", text=f"ПОМИЛКА: Файл '{file_path}' не знайдено.")]
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return [types.TextContent(type="text", text=content)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"ПОМИЛКА при читанні файлу: {str(e)}")]

    raise ValueError(f"Невідомий інструмент: {name}")


# --- РЕСУРСИ (RESOURCES) ---
@server.read_resource()
async def read_resource_handler(uri: str) -> str:
    """Отримання даних за URI-схемою file:///"""
    if uri.startswith("file:///"):
        relative_path = uri.replace("file:///", "")
        if os.path.exists(relative_path):
            with open(relative_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            raise ValueError(f"Ресурс за шляхом {relative_path} відсутній.")
    raise ValueError(f"Непідтримуваний формат URI: {uri}")


# --- ПРОМПТИ (PROMPTS) ---
@server.get_prompt()
async def get_prompt_handler(name: str, arguments: dict | None) -> types.GetPromptResult:
    """Генерація параметризованих шаблонів взаємодії"""
    if name == "system_audit":
        target = arguments.get("target", "system") if arguments else "system"
        return types.GetPromptResult(
            description="Шаблон аудіту системної безпеки",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Проведіть повний аналіз логів та конфігурації для компонента: {target}. Виявте потенційні вразливості."
                    )
                )
            ]
        )
    raise ValueError(f"Невідомий шаблон промпта: {name}")


# =====================================================================
# 3. ТОЧКА ВХОДУ: stdio TRANSPORT
# =====================================================================
async def main():
    print("Enterprise Tools Server ініціалізується...", file=sys.stderr)

    init_options = InitializationOptions(
        server_name="enterprise-tools-server",
        server_version="1.0.0",
        capabilities=types.ServerCapabilities(
            tools=types.ToolsCapability(listChanged=False),
            resources=types.ResourcesCapability(subscribe=False, listChanged=False),
            prompts=types.PromptsCapability(listChanged=False)
        )
    )

    async with stdio_server() as (read_stream, write_stream):
        print("Сервер успішно підключився до транспортного каналу stdio і готовий до роботи!", file=sys.stderr)
        await server.run(
            read_stream,
            write_stream,
            init_options
        )


if __name__ == "__main__":
    asyncio.run(main())