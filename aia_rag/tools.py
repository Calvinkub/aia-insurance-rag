"""Allow-listed agent tools. Arguments are validated before use; results are returned as untrusted text."""
import ast
import operator

from pydantic import BaseModel, Field, ValidationError

from .retrieve import Retriever


class SearchArgs(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    product: str | None = Field(default=None, max_length=80)


class CalcArgs(BaseModel):
    expression: str = Field(min_length=1, max_length=120)


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.Mod: operator.mod}


def safe_eval(expr: str) -> float:
    """Arithmetic only: numbers and + - * / ** % with parentheses. No names, calls, or attributes."""
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("exponent too large")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("unsupported expression")
    return ev(ast.parse(expr.replace(",", ""), mode="eval"))


TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "search_brochures",
        "description": "Search AIA Thailand product brochures. Returns passages with product and page. Optionally restrict to one product name.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}, "product": {"type": "string", "description": "Optional product name filter, e.g. 'CI Care'"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "list_products",
        "description": "List all product names available in the brochure corpus.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "calculate",
        "description": "Evaluate an arithmetic expression, e.g. '1000000 * 1.4'. Use for any math instead of computing yourself.",
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}},
]


class ToolBox:
    def __init__(self, retriever: Retriever):
        self.retriever = retriever
        self._products = sorted({c["product"] for c in retriever.chunks})
        self.handlers = {"search_brochures": self._search, "list_products": self._list, "calculate": self._calc}

    def call(self, name: str, raw_args: dict) -> str:
        handler = self.handlers.get(name)  # allow-list: unknown tool names are rejected
        if handler is None:
            return f"ERROR: unknown tool {name!r}. Allowed: {sorted(self.handlers)}"
        try:
            return handler(raw_args or {})
        except (ValidationError, ValueError, ZeroDivisionError, SyntaxError) as e:
            return f"ERROR: {str(e)[:200]}"

    def _search(self, args: dict) -> str:
        a = SearchArgs.model_validate(args)
        hits = self.retriever.search(a.query, k=4, min_score=0.35, product=a.product)
        if not hits:
            return "No relevant passages found."
        return "\n\n".join(f"[{h.chunk['product']} p{h.chunk['page']}] {h.chunk['text']}" for h in hits)

    def _list(self, args: dict) -> str:
        return "\n".join(self._products)

    def _calc(self, args: dict) -> str:
        a = CalcArgs.model_validate(args)
        return str(round(float(safe_eval(a.expression)), 4))
