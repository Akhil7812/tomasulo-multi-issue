
from init import BTB_SIZE


def squash(m, br, cycle):
  
    dead = [i for i in m.rob if i.seq > br.seq]
    for i in dead:
        i.squashed = True
    m.stats['squashed'] += len(dead)
    while m.rob and m.rob[-1].seq > br.seq:
        m.rob.pop()
    for k in m.rs:
        m.rs[k] = [i for i in m.rs[k] if not i.squashed]
    m.lsq = [i for i in m.lsq if not i.squashed]
    m.inflight = [x for x in m.inflight if not x[1].squashed]
    m.pending = [x for x in m.pending if not x[1].squashed]
    for k, units in m.fus.items():
        for u in units:
            if u.last is not None and u.last.squashed:
                u.next_free = min(u.next_free, cycle + 1)
    if m.port_ins is not None and m.port_ins.squashed:
        m.port_ins = None; m.port_finish = None
        m.port_free = min(m.port_free, cycle + 1)
    for k in ('R', 'F'):
        m.rat[k] = [None if (p is None or p.committed) else p for p in br.rat_ckpt[k]]
    m.fetch_pc = br.actual_next
    m.fetch_resume = cycle + 2


def resolve_branch(m, ins, cycle):
    a, b = ins.src1.get(), ins.src2.get()
    taken = (a == b) if ins.st.op == 'Beq' else (a != b)
    target = ins.pc + 1 + ins.st.off
    ins.actual_next = target if taken else ins.pc + 1
    ins.resolved = cycle
    m.btb[ins.pc % BTB_SIZE] = [ins.pc, taken, target]         
    if ins.actual_next != ins.pred_next:
        m.stats['mispredicts'] += 1
        squash(m, ins, cycle)


def finish(m, ins, cycle):
    st = ins.st
    ins.ex_end = cycle
    if st.op in ('Ld', 'Sd'):
        ins.addr = ins.src1.get() + st.imm
        ins.addr_cycle = cycle
    elif st.op in ('Beq', 'Bne'):
        resolve_branch(m, ins, cycle)
    else:
        a, b = ins.src1.get(), ins.src2.get()
        if st.op in ('Add', 'Add.d', 'Addi'):
            ins.result = a + b
        elif st.op in ('Sub', 'Sub.d'):
            ins.result = a - b
        else:                                     
            ins.result = a * b
        m.pending.append((cycle + 1, ins))          


def complete(m, cycle):
    for fin, ins, cls in sorted([x for x in m.inflight if x[0] == cycle], key=lambda x: x[1].seq):
        if not ins.squashed:
            finish(m, ins, cycle)
    m.inflight = [x for x in m.inflight if x[0] > cycle and not x[1].squashed]


def exe(m, cycle):
    complete(m, cycle)

    for cls in ('int', 'fpadd', 'fpmul'):
        cands = sorted([i for i in m.rs[cls] if i.issue < cycle and i.src1.ready(cycle) and i.src2.ready(cycle)],
                       key=lambda i: i.seq)
        for ins in cands:
            fu = next((u for u in m.fus[cls] if u.next_free <= cycle), None)
            if fu is None:
                break
            dispatch(m, ins, cls, fu, cycle)
            m.rs[cls].remove(ins)
    cands = [i for i in m.lsq if not i.addr_started and i.issue < cycle and i.src1.ready(cycle)]
    for ins in cands:                              
        fu = next((u for u in m.fus['mem'] if u.next_free <= cycle), None)
        if fu is None:
            break
        ins.addr_started = True
        dispatch(m, ins, 'mem', fu, cycle)

    complete(m, cycle)


def dispatch(m, ins, cls, fu, cycle):
    E = m.cfg.units[cls].ex
    ins.ex_start = cycle
    fu.last = ins
    fu.next_free = cycle + 1 if m.pipelined[cls] else cycle + E
    m.inflight.append((cycle + E - 1, ins, cls))
