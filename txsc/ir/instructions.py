import copy

from bitcoin.core import _bignum
from bitcoin.core.script import CScriptOp
from bitcoin.core.scripteval import _CastToBool

from txsc.ir import linear_nodes
from txsc.ir import structural_nodes

# Constants for instructions type.
LINEAR = 1
STRUCTURAL = 2
def get_instructions_class(instructions_type):
    """Get the class for instructions of type instructions_type."""
    if instructions_type == LINEAR:
        return LInstructions
    elif instructions_type == STRUCTURAL:
        return SInstructions

class Instructions(object):
    """Base model for instructions."""
    pass

class LInstructions(Instructions, list):
    """Model for linear instructions."""
    ir_type = LINEAR

    def __init__(self, *args):
        # Perform a deep copy if an LInstructions instance is passed.
        if len(args) == 1 and isinstance(args[0], LInstructions):
            return super(LInstructions, self).__init__(copy.deepcopy(args[0]))
        return super(LInstructions, self).__init__(*args)

    def __str__(self):
        return str(map(str, self))

    def copy_slice(self, start, end):
        """Create a copy of instructions from [start : end]."""
        return copy.deepcopy(self[start:end])

    def replace_slice(self, start, end, values):
        """Replace instructions from [start : end] with values."""
        self[start:end] = values

    def matches_template(self, template, index, strict=True):
        """Returns whether a block that matches templates starts at index.

        If strict is True, then Push opcodes must push the same value that
        those in the template push.
        """
        for i in range(len(template)):
            if not template[i]:
                continue

            equal = template[i] == self[index + i]
            if strict and not equal:
                return False

            # Non-strict evaluation.
            template_item = template[i]
            script_item = self[index + i]
            if template_item.__class__.__name__ == 'SmallIntOpCode' and isinstance(script_item, linear_nodes.SmallIntOpCode):
                equal = True
            elif isinstance(template_item, linear_nodes.Push) and isinstance(script_item, linear_nodes.Push):
                equal = True

            if not equal:
                return False

        return True

    def replace(self, start, length, callback):
        """Pass [start : length] instructions to callback and replace them with its result."""
        end = start + length
        values = self.copy_slice(start, end)
        self.replace_slice(start, end, callback(values))

    def replace_template(self, template, callback, strict=True):
        """Call callback with any instructions matching template."""
        idx = 0
        while 1:
            if idx >= len(self):
                break
            if (idx <= len(self) - len(template)) and self.matches_template(template, idx, strict):
                self.replace(idx, len(template), callback)
                idx += len(template)
            else:
                idx += 1

    def find_occurrences(self, op):
        """Return all the indices that op occurs at."""
        occurrences = []
        template = [op]
        for i in range(len(self)):
            if self.matches_template(template, i):
                occurrences.append(i)
        return occurrences

class SInstructions(Instructions):
    """Model for structural instructions."""
    ir_type = STRUCTURAL
    def __init__(self, script=structural_nodes.Script()):
        self.script = script

    def dump(self, *args):
        return self.script.dump(*args)
