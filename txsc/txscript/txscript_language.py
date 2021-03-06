import ast
from ply import yacc

from txsc.ir.instructions import STRUCTURAL, SInstructions
from txsc.language import Language
from txsc.transformer import SourceVisitor
from txsc.txscript import ScriptParser, ScriptTransformer
from txsc.symbols import SymbolTable

def get_lang():
    return TxScriptLanguage

class TxScriptSourceVisitor(SourceVisitor):
    """Wrapper around txscript classes."""
    ir_type = STRUCTURAL
    def __init__(self, *args, **kwargs):
        super(TxScriptSourceVisitor, self).__init__(*args, **kwargs)
        # Set up yacc.
        self.parser = ScriptParser()

    def transform(self, source, symbol_table):
        if isinstance(source, list):
            source = '\n'.join(source)

        node = self.parser.parse(source)
        if not isinstance(node, ast.Module):
            node = ast.Module(body=node)
        ast.fix_missing_locations(node)

        # Convert AST to structural representation.
        node = ScriptTransformer(symbol_table).visit(node)

        return SInstructions(node)


class TxScriptLanguage(Language):
    """Python-based TxScript language."""
    name = 'txscript'
    source_visitor = TxScriptSourceVisitor
    supports_symbol_table = True
