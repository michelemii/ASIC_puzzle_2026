#!/usr/bin/env python3
import sys
import time
from pysat.formula import IDPool
from pysat.solvers import Cadical153

import sim as S

NBITS = int(sys.argv[1]) if len(sys.argv) > 1 else 121
TAIL = int(sys.argv[2]) if len(sys.argv) > 2 else 16
T0 = time.time()


def log(*a):
    print("[%6.1fs]" % (time.time() - T0), *a, flush=True)


class CNF:
    def __init__(self):
        self.pool = IDPool()
        self.cls = []
        self.true = self.pool.id("__true__")
        self.cls.append([self.true])
        self.cache = {}

    def new(self):
        return self.pool.id(("t", len(self.pool.obj2id)))

    def const(self, v):
        return self.true if v else -self.true

    def AND(self, a, b):
        if a == -self.true or b == -self.true:
            return -self.true
        if a == self.true:
            return b
        if b == self.true:
            return a
        if a == b:
            return a
        if a == -b:
            return -self.true
        k = ("and", min(a, b), max(a, b))
        if k in self.cache:
            return self.cache[k]
        o = self.new()
        self.cls += [[-o, a], [-o, b], [o, -a, -b]]
        self.cache[k] = o
        return o

    def OR(self, a, b):
        return -self.AND(-a, -b)

    def XOR(self, a, b):
        if a == self.true:
            return -b
        if a == -self.true:
            return b
        if b == self.true:
            return -a
        if b == -self.true:
            return a
        if a == b:
            return -self.true
        if a == -b:
            return self.true
        k = ("xor", min(abs(a), abs(b)), max(abs(a), abs(b)), (a < 0) ^ (b < 0))
        if k in self.cache:
            return self.cache[k]
        o = self.new()
        self.cls += [[-o, a, b], [-o, -a, -b], [o, -a, b], [o, a, -b]]
        self.cache[k] = o
        return o

    def MUX(self, s, a0, a1):
        return self.OR(self.AND(-s, a0), self.AND(s, a1))

    def ANDN(self, xs):
        r = self.true
        for x in xs:
            r = self.AND(r, x)
        return r

    def ORN(self, xs):
        r = -self.true
        for x in xs:
            r = self.OR(r, x)
        return r


def cell_out(f, k, c):
    """symbolic model of one standard cell, k = cell type, c = pin -> literal"""
    A, O, X, N = f.ANDN, f.ORN, f.XOR, lambda x: -x
    if k in ("buf_2", "clkbuf_4", "clkbuf_8", "clkbuf_16"):
        return {"X": c["A"]}
    if k == "inv_2":
        return {"Y": N(c["A"])}
    if k == "conb_1":
        return {"HI": f.const(1), "LO": f.const(0)}
    if k == "and2_2":
        return {"X": A([c["A"], c["B"]])}
    if k == "and3_2":
        return {"X": A([c["A"], c["B"], c["C"]])}
    if k == "and4_2":
        return {"X": A([c["A"], c["B"], c["C"], c["D"]])}
    if k == "and2b_2":
        return {"X": A([N(c["A_N"]), c["B"]])}
    if k == "and3b_2":
        return {"X": A([N(c["A_N"]), c["B"], c["C"]])}
    if k == "and4b_2":
        return {"X": A([N(c["A_N"]), c["B"], c["C"], c["D"]])}
    if k == "and4bb_2":
        return {"X": A([N(c["A_N"]), N(c["B_N"]), c["C"], c["D"]])}
    if k == "or2_2":
        return {"X": O([c["A"], c["B"]])}
    if k == "or3_2":
        return {"X": O([c["A"], c["B"], c["C"]])}
    if k == "or4_2":
        return {"X": O([c["A"], c["B"], c["C"], c["D"]])}
    if k == "or3b_2":
        return {"X": O([c["A"], c["B"], N(c["C_N"])])}
    if k == "or4b_2":
        return {"X": O([c["A"], c["B"], c["C"], N(c["D_N"])])}
    if k == "or4bb_2":
        return {"X": O([c["A"], c["B"], N(c["C_N"]), N(c["D_N"])])}
    if k == "nand2_2":
        return {"Y": N(A([c["A"], c["B"]]))}
    if k == "nand3_2":
        return {"Y": N(A([c["A"], c["B"], c["C"]]))}
    if k == "nand4_2":
        return {"Y": N(A([c["A"], c["B"], c["C"], c["D"]]))}
    if k == "nand2b_2":
        return {"Y": N(A([N(c["A_N"]), c["B"]]))}
    if k == "nand3b_2":
        return {"Y": N(A([N(c["A_N"]), c["B"], c["C"]]))}
    if k == "nor2_2":
        return {"Y": N(O([c["A"], c["B"]]))}
    if k == "nor3_2":
        return {"Y": N(O([c["A"], c["B"], c["C"]]))}
    if k == "nor4_2":
        return {"Y": N(O([c["A"], c["B"], c["C"], c["D"]]))}
    if k == "nor3b_2":
        return {"Y": N(O([c["A"], c["B"], N(c["C_N"])]))}
    if k == "nor4b_2":
        return {"Y": N(O([c["A"], c["B"], c["C"], N(c["D_N"])]))}
    if k == "xor2_2":
        return {"X": X(c["A"], c["B"])}
    if k == "xnor2_2":
        return {"Y": N(X(c["A"], c["B"]))}
    if k == "mux2_1":
        return {"X": f.MUX(c["S"], c["A0"], c["A1"])}
    if k == "a21o_2":
        return {"X": O([A([c["A1"], c["A2"]]), c["B1"]])}
    if k == "a21oi_2":
        return {"Y": N(O([A([c["A1"], c["A2"]]), c["B1"]]))}
    if k == "a21bo_2":
        return {"X": O([A([c["A1"], c["A2"]]), N(c["B1_N"])])}
    if k == "a21boi_2":
        return {"Y": N(O([A([c["A1"], c["A2"]]), N(c["B1_N"])]))}
    if k == "a22o_2":
        return {"X": O([A([c["A1"], c["A2"]]), A([c["B1"], c["B2"]])])}
    if k == "a22oi_2":
        return {"Y": N(O([A([c["A1"], c["A2"]]), A([c["B1"], c["B2"]])]))}
    if k == "a31o_2":
        return {"X": O([A([c["A1"], c["A2"], c["A3"]]), c["B1"]])}
    if k == "a31oi_2":
        return {"Y": N(O([A([c["A1"], c["A2"], c["A3"]]), c["B1"]]))}
    if k == "a32o_2":
        return {"X": O([A([c["A1"], c["A2"], c["A3"]]), A([c["B1"], c["B2"]])])}
    if k == "a41oi_2":
        return {"Y": N(O([A([c["A1"], c["A2"], c["A3"], c["A4"]]), c["B1"]]))}
    if k == "a211o_2":
        return {"X": O([A([c["A1"], c["A2"]]), c["B1"], c["C1"]])}
    if k == "a211oi_2":
        return {"Y": N(O([A([c["A1"], c["A2"]]), c["B1"], c["C1"]]))}
    if k == "a221o_2":
        return {"X": O([A([c["A1"], c["A2"]]), A([c["B1"], c["B2"]]), c["C1"]])}
    if k == "a221oi_2":
        return {"Y": N(O([A([c["A1"], c["A2"]]), A([c["B1"], c["B2"]]), c["C1"]]))}
    if k == "a311o_2":
        return {"X": O([A([c["A1"], c["A2"], c["A3"]]), c["B1"], c["C1"]])}
    if k == "a2111oi_2":
        return {"Y": N(O([A([c["A1"], c["A2"]]), c["B1"], c["C1"], c["D1"]]))}
    if k == "o21a_2":
        return {"X": A([O([c["A1"], c["A2"]]), c["B1"]])}
    if k == "o21ai_2":
        return {"Y": N(A([O([c["A1"], c["A2"]]), c["B1"]]))}
    if k == "o21ba_2":
        return {"X": A([O([c["A1"], c["A2"]]), N(c["B1_N"])])}
    if k == "o21bai_2":
        return {"Y": N(A([O([c["A1"], c["A2"]]), N(c["B1_N"])]))}
    if k == "o22a_2":
        return {"X": A([O([c["A1"], c["A2"]]), O([c["B1"], c["B2"]])])}
    if k == "o22ai_2":
        return {"Y": N(A([O([c["A1"], c["A2"]]), O([c["B1"], c["B2"]])]))}
    if k == "o31a_2":
        return {"X": A([O([c["A1"], c["A2"], c["A3"]]), c["B1"]])}
    if k == "o31ai_2":
        return {"Y": N(A([O([c["A1"], c["A2"], c["A3"]]), c["B1"]]))}
    if k == "o32a_2":
        return {"X": A([O([c["A1"], c["A2"], c["A3"]]), O([c["B1"], c["B2"]])])}
    if k == "o32ai_2":
        return {"Y": N(A([O([c["A1"], c["A2"], c["A3"]]), O([c["B1"], c["B2"]])]))}
    if k == "o211a_2":
        return {"X": A([O([c["A1"], c["A2"]]), c["B1"], c["C1"]])}
    if k == "o211ai_2":
        return {"Y": N(A([O([c["A1"], c["A2"]]), c["B1"], c["C1"]]))}
    if k == "o221a_2":
        return {"X": A([O([c["A1"], c["A2"]]), O([c["B1"], c["B2"]]), c["C1"]])}
    if k == "o311a_2":
        return {"X": A([O([c["A1"], c["A2"], c["A3"]]), c["B1"], c["C1"]])}
    if k == "o2bb2a_2":
        return {"X": A([N(A([c["A1_N"], c["A2_N"]])), O([c["B1"], c["B2"]])])}
    raise SystemExit("no symbolic model for %s" % k)


def main():
    d = S.Design()
    log("design: %d gates, %d flops" % (len(d.comb), len(d.flop)))

    # concrete reset state
    for _ in range(4):
        d.apply_async({"clk": 0, "rst_n": 0, "enable": 0, "I": 0})
        d.posedge()
    q0 = dict(d.q)
    log("reset state captured, %d flops set" % sum(q0.values()))

    portnets = set(v for v in d.ports.values() if v is not None)
    used = set()
    for it in d.insts:
        for p, n in it["conns"].items():
            if p not in S.OUTPINS:
                used.add(n)
    dangling = sorted(used - set(d.driver) - portnets - {d.vdd, d.vss}
                      - set(d.insts[i]["conns"]["Q"] for i in d.flop))
    log("undriven internal nets tied to 0: %s" % dangling)

    f = CNF()
    q = {i: f.const(q0[i]) for i in d.flop}
    inbits = []
    succ = []

    ncyc = NBITS + TAIL
    for t in range(ncyc):
        enabled = t < NBITS
        if enabled:
            b = f.new()
            inbits.append(b)
        else:
            b = f.const(0)
        val = {}
        for n in dangling:
            val[n] = f.const(0)
        val[d.vdd] = f.const(1)
        val[d.vss] = f.const(0)
        val[d.ports["clk"]] = f.const(0)
        val[d.ports["rst_n"]] = f.const(1)
        val[d.ports["enable"]] = f.const(1 if enabled else 0)
        val[d.ports["I"]] = b
        for i in d.flop:
            val[d.insts[i]["conns"]["Q"]] = q[i]
        for i in d.order:
            it = d.insts[i]
            c = {p: val[n] for p, n in it["conns"].items() if p not in S.OUTPINS}
            for p, lit in cell_out(f, it["cell"], c).items():
                val[it["conns"][p]] = lit
        succ.append(val[d.ports["success"]])
        nq = {}
        for i in d.flop:
            it = d.insts[i]
            cn = it["conns"]
            k = it["cell"]
            dd = val[cn["D"]]
            if k == "dfrtp_2":
                nq[i] = f.AND(val[cn["RESET_B"]], dd)
            elif k == "dfstp_2":
                nq[i] = f.OR(-val[cn["SET_B"]], dd)
            else:
                nq[i] = dd
        q = nq
        if t % 20 == 0:
            log("unrolled cycle %d, %d clauses" % (t, len(f.cls)))

    f.cls.append([s for s in succ[NBITS:]])
    log("cnf: %d vars, %d clauses" % (f.pool.top, len(f.cls)))

    s = Cadical153(bootstrap_with=f.cls)
    log("solving")
    sat = s.solve()
    log("result: %s" % sat)
    if not sat:
        print("UNSAT for NBITS=%d" % NBITS)
        return
    model = set(l for l in s.get_model() if l > 0)
    bits = "".join("1" if b in model else "0" for b in inbits)
    print("candidate bits (%d):" % len(bits))
    print(bits)
    tr = S.run(bits, tail=TAIL + 24)
    txt = "".join(chr(o) for o, _ in tr if 32 <= o < 127)
    print("VERIFIED simulation output:", repr(txt))
    print("success asserted:", any(x for _, x in tr))
    open("C:/.../solution.txt", "w").write(bits + "\n" + txt + "\n") # put your path here


if __name__ == "__main__":
    main()
