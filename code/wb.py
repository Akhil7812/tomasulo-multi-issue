

def wb(m, cycle):
    ready = sorted([x for x in m.pending if x[0] <= cycle], key=lambda x: (x[0], x[1].seq))
    for avail, ins in ready[:m.cdb_w]:
        ins.wb = cycle
        m.pending.remove((avail, ins))
