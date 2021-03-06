"""Script optimizations."""
import itertools

from txsc.ir.linear_context import LinearContextualizer, LinearInliner
import txsc.ir.linear_nodes as types

peephole_optimizers = []

def peephole(func):
    """Decorator for peephole optimizers."""
    peephole_optimizers.append(func)
    return func

def permutations(nodes):
    """Return permutations of nodes."""
    return [list(i) for i in itertools.permutations(nodes, len(nodes))]

@peephole
def merge_op_and_verify(instructions):
    """Merge opcodes with a corresponding *VERIFY form.

    e.g. OP_EQUAL OP_VERIFY -> OP_EQUALVERIFY
    """
    optimizations = []
    for op in types.iter_opcode_classes():
        if op.name.endswith('VERIFY') and op.name != 'OP_VERIFY':
            base_op = types.opcode_by_name(op.name[:-6])
            if not base_op:
                continue
            template = [base_op(), types.Verify()]
            optimizations.append((template, [op()]))

    for template, replacement in optimizations:
        callback = lambda values, replacement=replacement: replacement
        instructions.replace_template(template, callback)

@peephole
def replace_repeated_ops(instructions):
    """Replace repeated opcodes with single opcodes."""
    optimizations = [
        # OP_DROP OP_DROP -> OP_2DROP
        ([types.Drop(), types.Drop()], [types.TwoDrop()]),
    ]
    for template, replacement in optimizations:
        callback = lambda values, replacement=replacement: replacement
        instructions.replace_template(template, callback)

@peephole
def optimize_stack_ops(instructions):
    """Optimize stack operations."""
    for template, replacement in [
        # OP_1 OP_PICK -> OP_OVER
        ([types.One(), types.Pick()], [types.Over()]),
        # OP_1 OP_ROLL OP_DROP -> OP_NIP
        ([types.One(), types.Roll(), types.Drop()], [types.Nip()]),
        # OP_0 OP_PICK -> OP_DUP
        ([types.Zero(), types.Pick()], [types.Dup()]),
        # OP_0 OP_ROLL -> _
        ([types.Zero(), types.Roll()], []),
        # OP_1 OP_ROLL OP_1 OP_ROLL -> _
        ([types.One(), types.Roll(), types.One(), types.Roll()], []),
        # OP_1 OP_ROLL -> OP_SWAP
        ([types.One(), types.Roll()], [types.Swap()]),
    ]:
        callback = lambda values, replacement=replacement: replacement
        instructions.replace_template(template, callback)

@peephole
def replace_shortcut_ops(instructions):
    """Replace opcodes with a corresponding shortcut form."""
    optimizations = []
    # Replace division by 2.
    optimizations.append(([types.Two(), types.Div()], lambda values: [types.Div2()]))
    # Replace subtraction by 1.
    optimizations.append(([types.One(), types.Sub()], lambda values: [types.Sub1()]))
    # Replace 1 * -1 with -1.
    optimizations.append(([types.One(), types.Negate()], lambda values: [types.NegativeOne()]))
    # Replace addition by 1.
    for permutation in permutations([types.Push(), types.One()]):
        idx = 0 if isinstance(permutation[0], types.Push) else 1
        optimizations.append((permutation + [types.Add()], lambda values, idx=idx: [values[idx], types.Add1()]))
    for permutation in permutations([types.SmallIntOpCode(), types.One()]):
        idx = 0 if not isinstance(permutation[0], types.One) else 1
        optimizations.append((permutation + [types.Add()], lambda values, idx=idx: [values[idx], types.Add1()]))
    # Replace multiplication by 2.
    for permutation in permutations([types.Push(), types.Two()]):
        idx = 0 if isinstance(permutation[0], types.Push) else 1
        optimizations.append((permutation + [types.Mul()], lambda values, idx=idx: [values[idx], types.Mul2()]))
    for permutation in permutations([types.SmallIntOpCode(), types.Two()]):
        idx = 0 if not isinstance(permutation[0], types.Two) else 1
        optimizations.append((permutation + [types.Mul()], lambda values, idx=idx: [values[idx], types.Mul2()]))


    for template, callback in optimizations:
        instructions.replace_template(template, callback, strict=False)

@peephole
def replace_null_ops(instructions):
    """Replace operations that do nothing."""
    # Remove subtraction by 0.
    optimizations = [([types.Zero(), types.Sub()], lambda values: [])]
    # Remove addition by 0.
    for permutation in permutations([None, types.Zero()]):
        idx = 0 if permutation[0] is None else 1
        optimizations.append((permutation + [types.Add()], lambda values, idx=idx: [values[idx]]))

    for template, callback in optimizations:
        instructions.replace_template(template, callback)

@peephole
def optimize_dup_and_checksig(instructions):
    for template, callback in [
        ([types.Dup(), None, types.CheckSig()], lambda values: values[1:]),
    ]:
        instructions.replace_template(template, callback)

@peephole
def optimize_hashes(instructions):
    for template, replacement in [
        # OP_SHA256 OP_SHA256 -> OP_HASH256
        ([types.Sha256(), types.Sha256()], [types.Hash256()]),
        # OP_SHA256 OP_RIPEMD160 -> OP_HASH160
        ([types.Sha256(), types.RipeMD160()], [types.Hash160()]),
    ]:
        callback = lambda values, replacement=replacement: replacement
        instructions.replace_template(template, callback)

@peephole
def remove_trailing_verifications(instructions):
    """Remove any trailing OP_VERIFY occurrences.

    A trailing OP_VERIFY is redundant since a truthy value
    is required for a script to pass.
    """
    while len(instructions) and isinstance(instructions[-1], types.Verify):
        instructions.pop(-1)

@peephole
def promote_return(instructions):
    """Place any OP_RETURN occurrence at the beginning of the script."""
    # Get the indices of all OP_RETURN occurrences.
    occurrences = instructions.find_occurrences(types.Return())
    if not occurrences or occurrences == [0]:
        return
    map(instructions.pop, reversed(occurrences))
    instructions.insert(0, types.Return())

class PeepholeOptimizer(object):
    """Performs peephole optimization on the linear IR."""
    MAX_PASSES = 5
    def __init__(self, enabled=True):
        self.enabled = enabled

    def optimize(self, instructions, max_passes=-1):
        if not self.enabled:
            return
        if max_passes == -1:
            max_passes = self.MAX_PASSES

        pass_number = 0
        while 1:
            if pass_number > max_passes:
                break

            state = str(instructions)
            for func in peephole_optimizers:
                func(instructions)
            new = str(instructions)

            pass_number += 1

            if state == new:
                break

class LinearOptimizer(object):
    """Performs optimizations on the linear IR."""
    def optimize(self, instructions, peephole=True, inline=True):
        self.peephole_optimizer = PeepholeOptimizer(peephole)
        if inline:
            contextualizer = LinearContextualizer()
            inliner = LinearInliner()
            inliner.inline(instructions, contextualizer, self.peephole_optimizer)

        self.peephole_optimizer.optimize(instructions)
