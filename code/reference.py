from init import MEM_SIZE


def run_reference(cfg, prog, max_steps=1000000):
    regs = {'R': [0] * 32, 'F': [0.0] * 32}
    for i, v in cfg.regs_int.items(): regs['R'][i] = v
    for i, v in cfg.regs_fp.items(): regs['F'][i] = v
    mem = [0] * MEM_SIZE
    for a, v in cfg.mem_init.items(): mem[a] = v
    pc, steps = 0, 0
    while 0 <= pc < len(prog):
        steps += 1
        if steps > max_steps:
            raise RuntimeError('reference: infinite loop')
        s = prog[pc]
        op = s.op
        g = lambda r: 0 if r == ('R', 0) else regs[r[0]][r[1]]

        def put(r, v):
            if r != ('R', 0): regs[r[0]][r[1]] = v
        npc = pc + 1
        if op == 'Ld': put(s.rd, mem[g(s.rs) + s.imm])
        elif op == 'Sd': mem[g(s.rs) + s.imm] = g(s.rd)
        elif op == 'Beq':
            if g(s.rs) == g(s.rt): npc = pc + 1 + s.off
        elif op == 'Bne':
            if g(s.rs) != g(s.rt): npc = pc + 1 + s.off
        elif op in ('Add', 'Add.d'): put(s.rd, g(s.rs) + g(s.rt))
        elif op in ('Sub', 'Sub.d'): put(s.rd, g(s.rs) - g(s.rt))
        elif op == 'Addi': put(s.rd, g(s.rs) + s.imm)
        elif op == 'Mult.d': put(s.rd, g(s.rs) * g(s.rt))
        pc = npc
    return regs, mem, steps
