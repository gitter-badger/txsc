"""Script optimizations."""

import txsc.ir.linear_nodes as types

optimizers = []

def op_by_name(name):
    """Get the linear representation class for name."""
    return types.opcode_classes[name]

def optimizer(func):
    """Decorator for optimizers."""
    optimizers.append(func)
    return func

@optimizer
def merge_op_and_verify(instructions):
    """Merge opcodes with a corresponding *VERIFY form.

    e.g. OP_EQUAL OP_VERIFY -> OP_EQUALVERIFY
    """
    optimizations = []
    for op_name, op in types.opcode_classes.items():
        if op_name.endswith('VERIFY') and op_name != 'OP_VERIFY':
            try:
                base_op = op_by_name(op_name[:-6])
            except KeyError:
                continue
            else:
                template = [base_op(), types.Verify()]
                optimizations.append((template, [op()]))

    for template, replacement in optimizations:
        callback = lambda values, replacement=replacement: replacement
        instructions.replace_template(template, callback)

@optimizer
def replace_repeated_ops(instructions):
    """Replace repeated opcodes with single opcodes."""
    optimizations = [
        # OP_DROP OP_DROP -> OP_2DROP
        ([types.Drop(), types.Drop()], [types.TwoDrop()]),
    ]
    for template, replacement in optimizations:
        callback = lambda values, replacement=replacement: replacement
        instructions.replace_template(template, callback)

@optimizer
def optimize_stack_ops(instructions):
    """Optimize stack operations."""
    for template, replacement in [
        # OP_1 OP_PICK -> OP_OVER
        ([types.One(), types.Pick()], [types.Over()]),
        # OP_1 OP_ROLL OP_DROP -> OP_NIP
        ([types.One(), types.Roll(), types.Drop()], [types.Nip()]),
        # OP_0 OP_PICK -> OP_DUP
        ([types.Zero(), types.Pick()], [types.Dup()]),
    ]:
        callback = lambda values, replacement=replacement: replacement
        instructions.replace_template(template, callback)

@optimizer
def replace_shortcut_ops(instructions):
    """Replace opcodes with a corresponding shortcut form."""
    optimizations = [
        # OP_1 OP_ADD -> OP_1ADD
        ([types.One(), types.Add()], [types.Add1()]),
        # OP_1 OP_SUB -> OP_1SUB
        ([types.One(), types.Sub()], [types.Sub1()]),
        # OP_2 OP_MUL -> OP_2MUL
        ([types.Two(), types.Mul()], [types.Mul2()]),
        # OP_2 OP_DIV -> OP_2DIV
        ([types.Two(), types.Div()], [types.Div2()]),
        # OP_1 OP_NEGATE -> OP_1NEGATE
        ([types.One(), types.Negate()], [types.NegativeOne()]),
    ]
    for template, replacement in optimizations:
        callback = lambda values, replacement=replacement: replacement
        instructions.replace_template(template, callback)

@optimizer
def optimize_dup_and_checksig(instructions):
    for template, callback in [
        ([types.Dup(), None, types.CheckSig()], lambda values: values[1:]),
    ]:
        instructions.replace_template(template, callback)

@optimizer
def optimize_hashes(instructions):
    for template, replacement in [
        # OP_SHA256 OP_SHA256 -> OP_HASH256
        ([types.Sha256(), types.Sha256()], [types.Hash256()]),
        # OP_SHA256 OP_RIPEMD160 -> OP_HASH160
        ([types.Sha256(), types.RipeMD160()], [types.Hash160()]),
    ]:
        callback = lambda values, replacement=replacement: replacement
        instructions.replace_template(template, callback)

@optimizer
def remove_trailing_verifications(instructions):
    """Remove any trailing OP_VERIFY occurrences.

    A trailing OP_VERIFY is redundant since a truthy value
    is required for a script to pass.
    """
    while isinstance(instructions[-1], types.Verify):
        instructions.pop(-1)

class Optimizer(object):
    def __init__(self, debug=False):
        self.debug = debug

    def debug_print(self, s):
        if self.debug:
            print('[%s] %s' % (self.__class__.__name__, s))

    def optimize(self, instructions):
        for func in optimizers:
            func(instructions)