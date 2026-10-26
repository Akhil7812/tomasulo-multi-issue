
import re
from collections import deque

OPCODES = {'ld': 'Ld', 'sd': 'Sd', 'beq': 'Beq', 'bne': 'Bne', 'add': 'Add',
           'add.d': 'Add.d', 'addi': 'Addi', 'sub': 'Sub', 'sub.d': 'Sub.d',
           'mult.d': 'Mult.d'}
CLASS = {'Add': 'int', 'Addi': 'int', 'Sub': 'int', 'Beq': 'int', 'Bne': 'int',
         'Add.d': 'fpadd', 'Sub.d': 'fpadd', 'Mult.d': 'fpmul',
         'Ld': 'mem', 'Sd': 'mem'}
MEM_SIZE = 256          
BTB_SIZE = 8


def num(s):
    s = s.strip()
    return int(s) if re.fullmatch(r'[-+]?\d+', s) else float(s)



class UnitCfg:
    def __init__(self, rs, ex, mem, fus):
        self.rs, self.ex, self.mem, self.fus = rs, ex, mem, fus


class Config:
    def __init__(self):
        self.units = {'int': UnitCfg(2, 1, None, 1),
                      'fpadd': UnitCfg(3, 3, None, 1),
                      'fpmul': UnitCfg(2, 20, None, 1),
                      'mem': UnitCfg(3, 1, 4, 1)}
        self.rob_size = 128
        self.issue_width = 1        
        self.cdb_width = None      
        self.commit_width = None    
        self.regs_int = {}
        self.regs_fp = {}
        self.mem_init = {}


class StaticIns:
    """one line of the program"""
    def __init__(self, text, op, rd=None, rs=None, rt=None, imm=0, off=0):
        self.text, self.op, self.rd, self.rs, self.rt = text, op, rd, rs, rt
        self.imm, self.off = imm, off
        self.cls = CLASS[op]


def parse_reg(tok):
    tok = tok.strip().upper()
    m = re.fullmatch(r'([RF])(\d+)', tok)
    if not m or not 0 <= int(m.group(2)) < 32:
        raise ValueError('bad register: ' + tok)
    return (m.group(1), int(m.group(2)))


def parse_instruction(line):
    toks = line.replace(',', ' ').split()
    op = OPCODES[toks[0].lower()]
    a = toks[1:]
    if op in ('Ld', 'Sd'):
        m = re.fullmatch(r'(-?\d+)\((\w+)\)', a[1])
        if not m:
            raise ValueError('bad memory operand: ' + line)
        ins = StaticIns('', op, rd=parse_reg(a[0]), rs=parse_reg(m.group(2)), imm=int(m.group(1)))
        if ins.rd[0] != 'F' or ins.rs[0] != 'R':
            raise ValueError('Ld/Sd need an F data register and an R base register: ' + line)
        txt = '%s %s, %d(%s%d)' % (op, a[0].upper(), ins.imm, ins.rs[0], ins.rs[1])
    elif op in ('Beq', 'Bne'):
        ins = StaticIns('', op, rs=parse_reg(a[0]), rt=parse_reg(a[1]), off=int(a[2]))
        txt = '%s %s, %s, %d' % (op, a[0].upper(), a[1].upper(), ins.off)
    elif op == 'Addi':
        ins = StaticIns('', op, rd=parse_reg(a[0]), rs=parse_reg(a[1]), imm=int(a[2]))
        txt = '%s %s, %s, %d' % (op, a[0].upper(), a[1].upper(), ins.imm)
    else:
        ins = StaticIns('', op, rd=parse_reg(a[0]), rs=parse_reg(a[1]), rt=parse_reg(a[2]))
        txt = '%s %s, %s, %s' % (op, a[0].upper(), a[1].upper(), a[2].upper())
    want = 'F' if op in ('Add.d', 'Sub.d', 'Mult.d') else 'R'
    if op not in ('Ld', 'Sd', 'Beq', 'Bne'):
        for r in (ins.rd, ins.rs, ins.rt):
            if r is not None and r[0] != want:
                raise ValueError('wrong register type: ' + line)
    ins.text = txt
    return ins


def read_input(path):
    """returns (Config, [StaticIns])"""
    cfg, prog = Config(), []
    labels = [('integer adder', 'int'), ('fp adder', 'fpadd'), ('fp multiplier', 'fpmul'),
              ('load/store unit', 'mem')]
    with open(path) as f:
        lines = f.read().splitlines()
    for raw in lines:
        line = raw.split('#')[0].strip() if not raw.strip().startswith('#') else ''
        if not line:
            continue
        low = line.lower()
        first = low.replace(',', ' ').split()[0]
        if first in OPCODES:                                  
            prog.append(parse_instruction(line))
            continue
        hit = False
        for lab, key in labels:                               
            if low.startswith(lab):
                t = line[len(lab):].split()
                if key == 'mem' or len(t) == 4:
                    t = [None if x in ('-', '_') else int(x) for x in t]
                    while len(t) < 4:
                        t.append(None)
                    cfg.units[key] = UnitCfg(t[0], t[1], t[2], t[3] or 1)
                else:                                         
                    cfg.units[key] = UnitCfg(int(t[0]), int(t[1]), None, int(t[2]) if len(t) > 2 else 1)
                hit = True
                break
        if hit:
            continue
        m = re.match(r'rob entries\s*=\s*(\d+)', low)
        if m:
            cfg.rob_size = int(m.group(1)); continue
        m = re.match(r'issue width\s*=\s*(\d+)', low)
        if m:
            cfg.issue_width = int(m.group(1)); continue
        m = re.match(r'cdb width\s*=\s*(\d+)', low)
        if m:
            cfg.cdb_width = int(m.group(1)); continue
        m = re.match(r'commit width\s*=\s*(\d+)', low)
        if m:
            cfg.commit_width = int(m.group(1)); continue
        for mm in re.finditer(r'mem\[(\d+)\]\s*=\s*([-+\d.eE]+)', low):
            cfg.mem_init[int(mm.group(1))] = num(mm.group(2))
        for mm in re.finditer(r'(?<![\w\[])([rf])(\d+)\s*=\s*([-+\d.eE]+)', low):
            v = num(mm.group(3))
            if mm.group(1) == 'r':
                cfg.regs_int[int(mm.group(2))] = int(v)
            else:
                cfg.regs_fp[int(mm.group(2))] = float(v)
    return cfg, prog



class Opnd:
    """a source operand: either a value, or a pointer to the producing (in-flight) instruction"""
    def __init__(self, prod, val):
        self.prod, self.val = prod, val

    def ready(self, cycle):
        return self.prod is None or (self.prod.wb is not None and self.prod.wb < cycle)

    def get(self):
        return self.val if self.prod is None else self.prod.result


class Ins:
    """dynamic instruction = ROB entry (+ RS / LSQ info)"""
    def __init__(self, seq, pc, st):
        self.seq, self.pc, self.st = seq, pc, st
        self.src1 = self.src2 = None
        self.dest = None            
        self.result = None
        self.issue = self.ex_start = self.ex_end = None
        self.mem_start = self.mem_end = self.wb = self.commit = None
        self.addr = None; self.addr_cycle = None; self.addr_started = False   
        self.pred_taken = False; self.pred_next = None; self.rat_ckpt = None  
        self.actual_next = None; self.resolved = None
        self.squashed = False; self.committed = False; self.forwarded = False


class FU:
    def __init__(self):
        self.next_free = 0
        self.last = None


class Machine:
    def __init__(self, cfg, prog):
        self.cfg, self.prog = cfg, prog
        self.W = cfg.issue_width
        self.cdb_w = cfg.cdb_width or self.W
        self.commit_w = cfg.commit_width or self.W
        self.regs = {'R': [0] * 32, 'F': [0.0] * 32}
        for i, v in cfg.regs_int.items(): self.regs['R'][i] = v
        for i, v in cfg.regs_fp.items(): self.regs['F'][i] = v
        self.rat = {'R': [None] * 32, 'F': [None] * 32}
        self.memory = [0] * MEM_SIZE
        for a, v in cfg.mem_init.items():
            if not 0 <= a < MEM_SIZE:
                raise ValueError('Mem[%d] outside the 256B memory' % a)
            self.memory[a] = v
        self.rob = deque()
        self.rs = {'int': [], 'fpadd': [], 'fpmul': []}
        self.lsq = []                               
        self.fus = {k: [FU() for _ in range(cfg.units[k].fus)] for k in ('int', 'fpadd', 'fpmul', 'mem')}
        self.pipelined = {'int': False, 'fpadd': True, 'fpmul': True, 'mem': False}
        self.inflight = []                          
        self.pending = []                           
        self.port_free = 0                          
        self.port_ins = None; self.port_finish = None
        self.btb = [None] * BTB_SIZE                
        self.fetch_pc = 0
        self.fetch_resume = 1
        self.seq = 0
        self.log = []                               
        self.stats = dict(branches=0, mispredicts=0, squashed=0)

    def done(self):
        return not self.rob and not (0 <= self.fetch_pc < len(self.prog))
