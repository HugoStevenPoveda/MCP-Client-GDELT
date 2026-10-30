from fastmcp import Client
from cliente_mcp.utils.logger_config import setup_logger

setup_logger()


class MCPClient:
    """
    Cliente MCP para comunicación con servidores MCP.

    Responsabilidades:
    - Conectar a servidores MCP
    - Listar tools disponibles
    - Mapear tools a sus clientes
    - Proporcionar acceso a clientes MCP
    """

    def __init__(self, server_urls):
        """
        Inicializa el cliente MCP.

        Args:
            server_urls: Lista de {"name": "GDELT", "url": "http://..."}
        """
        self.servers = server_urls
        self.mcp_clients = {}
        self.available_tools = []
        self.tool_to_client = {}  # Mapeo tool_name -> client

        # Crear clientes MCP para cada servidor
        for server in self.servers:
            self.mcp_clients[server["name"]] = Client(server["url"])

        print(f"\n💰 [CLIENT.__init__] Configuración de servidores MCP:")
        for server in self.servers:
            print(f"      - {server['name']}: {server['url']}")
        print("─"*70 + "\n")

    async def connect(self):
        """Conecta a todos los servidores MCP y lista sus tools."""
        print("\n🔧 [CLIENT.connect] Listando tools disponibles de cada servidor...")
        self.available_tools = []

        for server_name, client in self.mcp_clients.items():
            try:
                print(f"\n   ▸ Consultando tools de {server_name}...")
                async with client:
                    tools = await client.list_tools()
                    print(f"      ✓ {server_name}: {len(tools)} tools encontradas")
                    for tool in tools:
                        print(f"         • {tool.name}: {tool.description[:60]}...")
                        self.tool_to_client[tool.name] = client
                    self.available_tools.extend(tools)
            except Exception as e:
                print(f"      ✗ Error con {server_name}: {e}")

        print(f"\n   ▸ Servidores conectados: {len(self.mcp_clients)}")
        print(f"   ▸ Total tools MCP: {len(self.available_tools)}")
        print("─"*70 + "\n")
        return self.available_tools

    async def disconnect(self):
        """Desconecta de todos los servidores MCP."""
        print("\n👋 Cerrando cliente MCP...")

    def list_tools(self):
        """
        Devuelve lista de tools MCP disponibles.

        Returns:
            Lista de tools MCP
        """
        return self.available_tools

    def get_tool_client(self, tool_name: str):
        """
        Obtiene el cliente MCP correcto para una tool.

        Args:
            tool_name: Nombre de la tool

        Returns:
            Cliente MCP instance o None si no existe
        """
        return self.tool_to_client.get(tool_name)

    async def execute_tool(self, tool_name: str, params: dict):
        """
        Ejecuta una tool MCP directamente (método puro).

        Args:
            tool_name: Nombre de la tool
            params: Parámetros de la tool

        Returns:
            Resultado de la tool

        Raises:
            ValueError: Si la tool no existe
        """
        client = self.tool_to_client.get(tool_name)
        if not client:
            raise ValueError(f"Tool '{tool_name}' no encontrada en servidores MCP")

        async with client:
            result = await client.call_tool(tool_name, params)

        return result

    def get_servers_info(self):
        """
        Obtiene información de los servidores conectados.

        Returns:
            Dict con información de servidores
        """
        return {
            "total_servers": len(self.mcp_clients),
            "servers": [
                {
                    "name": server["name"],
                    "url": server["url"],
                    "tools_count": sum(
                        1 for tool_name, client in self.tool_to_client.items()
                        if client == self.mcp_clients[server["name"]]
                    )
                }
                for server in self.servers
            ],
            "total_tools": len(self.available_tools)
        }

    def __repr__(self):
        return (
            f"MCPClient(servers={len(self.mcp_clients)}, "
            f"tools={len(self.available_tools)})"
        )
