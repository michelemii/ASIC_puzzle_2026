#!/usr/bin/env python3
import json
import sys
from collections import defaultdict, deque

NETLIST = "C:/.../puzzle_netlist.json" # put your netlist path here

# cell models
def A(c, k):
    return c[k]


COMB = {
    "inv_2":      lambda c: {"Y": 1 - c["A"]},
    "buf_2":      lambda c: {"X": c["A"]},
    "clkbuf_4":   lambda c: {"X": c["A"]},
    "clkbuf_8":   lambda c: {"X": c["A"]},
    "clkbuf_16":  lambda c: {"X": c["A"]},

    "and2_2":     lambda c: {"X": c["A"] & c["B"]},
    "and3_2":     lambda c: {"X": c["A"] & c["B"] & c["C"]},
    "and4_2":     lambda c: {"X": c["A"] & c["B"] & c["C"] & c["D"]},
    "and2b_2":    lambda c: {"X": (1 - c["A_N"]) & c["B"]},
    "and3b_2":    lambda c: {"X": (1 - c["A_N"]) & c["B"] & c["C"]},
    "and4b_2":    lambda c: {"X": (1 - c["A_N"]) & c["B"] & c["C"] & c["D"]},
    "and4bb_2":   lambda c: {"X": (1 - c["A_N"]) & (1 - c["B_N"]) & c["C"] & c["D"]},

    "or2_2":      lambda c: {"X": c["A"] | c["B"]},
    "or3_2":      lambda c: {"X": c["A"] | c["B"] | c["C"]},
    "or4_2":      lambda c: {"X": c["A"] | c["B"] | c["C"] | c["D"]},
    "or3b_2":     lambda c: {"X": c["A"] | c["B"] | (1 - c["C_N"])},
    "or4b_2":     lambda c: {"X": c["A"] | c["B"] | c["C"] | (1 - c["D_N"])},
    "or4bb_2":    lambda c: {"X": c["A"] | c["B"] | (1 - c["C_N"]) | (1 - c["D_N"])},

    "nand2_2":    lambda c: {"Y": 1 - (c["A"] & c["B"])},
    "nand3_2":    lambda c: {"Y": 1 - (c["A"] & c["B"] & c["C"])},
    "nand4_2":    lambda c: {"Y": 1 - (c["A"] & c["B"] & c["C"] & c["D"])},
    "nand2b_2":   lambda c: {"Y": 1 - ((1 - c["A_N"]) & c["B"])},
    "nand3b_2":   lambda c: {"Y": 1 - ((1 - c["A_N"]) & c["B"] & c["C"])},

    "nor2_2":     lambda c: {"Y": 1 - (c["A"] | c["B"])},
    "nor3_2":     lambda c: {"Y": 1 - (c["A"] | c["B"] | c["C"])},
    "nor4_2":     lambda c: {"Y": 1 - (c["A"] | c["B"] | c["C"] | c["D"])},
    "nor3b_2":    lambda c: {"Y": 1 - (c["A"] | c["B"] | (1 - c["C_N"]))},
    "nor4b_2":    lambda c: {"Y": 1 - (c["A"] | c["B"] | c["C"] | (1 - c["D_N"]))},

    "xor2_2":     lambda c: {"X": c["A"] ^ c["B"]},
    "xnor2_2":    lambda c: {"Y": 1 - (c["A"] ^ c["B"])},
    "mux2_1":     lambda c: {"X": c["A1"] if c["S"] else c["A0"]},
    "conb_1":     lambda c: {"HI": 1, "LO": 0},

    "a21o_2":     lambda c: {"X": (c["A1"] & c["A2"]) | c["B1"]},
    "a21oi_2":    lambda c: {"Y": 1 - ((c["A1"] & c["A2"]) | c["B1"])},
    "a21bo_2":    lambda c: {"X": (c["A1"] & c["A2"]) | (1 - c["B1_N"])},
    "a21boi_2":   lambda c: {"Y": 1 - ((c["A1"] & c["A2"]) | (1 - c["B1_N"]))},
    "a22o_2":     lambda c: {"X": (c["A1"] & c["A2"]) | (c["B1"] & c["B2"])},
    "a22oi_2":    lambda c: {"Y": 1 - ((c["A1"] & c["A2"]) | (c["B1"] & c["B2"]))},
    "a31o_2":     lambda c: {"X": (c["A1"] & c["A2"] & c["A3"]) | c["B1"]},
    "a31oi_2":    lambda c: {"Y": 1 - ((c["A1"] & c["A2"] & c["A3"]) | c["B1"])},
    "a32o_2":     lambda c: {"X": (c["A1"] & c["A2"] & c["A3"]) | (c["B1"] & c["B2"])},
    "a41oi_2":    lambda c: {"Y": 1 - ((c["A1"] & c["A2"] & c["A3"] & c["A4"]) | c["B1"])},
    "a211o_2":    lambda c: {"X": (c["A1"] & c["A2"]) | c["B1"] | c["C1"]},
    "a211oi_2":   lambda c: {"Y": 1 - ((c["A1"] & c["A2"]) | c["B1"] | c["C1"])},
    "a221o_2":    lambda c: {"X": (c["A1"] & c["A2"]) | (c["B1"] & c["B2"]) | c["C1"]},
    "a221oi_2":   lambda c: {"Y": 1 - ((c["A1"] & c["A2"]) | (c["B1"] & c["B2"]) | c["C1"])},
    "a311o_2":    lambda c: {"X": (c["A1"] & c["A2"] & c["A3"]) | c["B1"] | c["C1"]},
    "a2111oi_2":  lambda c: {"Y": 1 - ((c["A1"] & c["A2"]) | c["B1"] | c["C1"] | c["D1"])},

    "o21a_2":     lambda c: {"X": (c["A1"] | c["A2"]) & c["B1"]},
    "o21ai_2":    lambda c: {"Y": 1 - ((c["A1"] | c["A2"]) & c["B1"])},
    "o21ba_2":    lambda c: {"X": (c["A1"] | c["A2"]) & (1 - c["B1_N"])},
    "o21bai_2":   lambda c: {"Y": 1 - ((c["A1"] | c["A2"]) & (1 - c["B1_N"]))},
    "o22a_2":     lambda c: {"X": (c["A1"] | c["A2"]) & (c["B1"] | c["B2"])},
    "o22ai_2":    lambda c: {"Y": 1 - ((c["A1"] | c["A2"]) & (c["B1"] | c["B2"]))},
    "o31a_2":     lambda c: {"X": (c["A1"] | c["A2"] | c["A3"]) & c["B1"]},
    "o31ai_2":    lambda c: {"Y": 1 - ((c["A1"] | c["A2"] | c["A3"]) & c["B1"])},
    "o32a_2":     lambda c: {"X": (c["A1"] | c["A2"] | c["A3"]) & (c["B1"] | c["B2"])},
    "o32ai_2":    lambda c: {"Y": 1 - ((c["A1"] | c["A2"] | c["A3"]) & (c["B1"] | c["B2"]))},
    "o211a_2":    lambda c: {"X": (c["A1"] | c["A2"]) & c["B1"] & c["C1"]},
    "o211ai_2":   lambda c: {"Y": 1 - ((c["A1"] | c["A2"]) & c["B1"] & c["C1"])},
    "o221a_2":    lambda c: {"X": (c["A1"] | c["A2"]) & (c["B1"] | c["B2"]) & c["C1"]},
    "o311a_2":    lambda c: {"X": (c["A1"] | c["A2"] | c["A3"]) & c["B1"] & c["C1"]},
    "o2bb2a_2":   lambda c: {"X": (1 - (c["A1_N"] & c["A2_N"])) & (c["B1"] | c["B2"])},
}

FLOPS = {"dfrtp_2", "dfstp_2", "dfxtp_2"}
OUTPINS = {"X", "Y", "Q", "HI", "LO"}


class Design:
    def __init__(self, path=NETLIST):
        d = json.load(open(path))
        self.insts = d["instances"]
        self.ports = d["ports"]
        self.vdd = d["vdd"]
        self.vss = d["vss"]

        self.comb = []
        self.flop = []
        for i, it in enumerate(self.insts):
            (self.flop if it["cell"] in FLOPS else self.comb).append(i)

        for i in self.comb:
            if self.insts[i]["cell"] not in COMB:
                raise SystemExit("missing model for %s" % self.insts[i]["cell"])

        # driver map: net -> (inst, pin)
        self.driver = {}
        for i, it in enumerate(self.insts):
            for p, n in it["conns"].items():
                if p in OUTPINS:
                    if n in self.driver:
                        raise SystemExit("net %d has two drivers" % n)
                    self.driver[n] = (i, p)

        # topological order over combinational instances
        deps = {i: set() for i in self.comb}
        users = defaultdict(list)
        for i in self.comb:
            for p, n in self.insts[i]["conns"].items():
                if p in OUTPINS:
                    continue
                src = self.driver.get(n)
                if src and src[0] in deps:
                    deps[i].add(src[0])
        for i in self.comb:
            for j in deps[i]:
                users[j].append(i)
        indeg = {i: len(deps[i]) for i in self.comb}
        q = deque(i for i in self.comb if indeg[i] == 0)
        order = []
        while q:
            i = q.popleft()
            order.append(i)
            for j in users[i]:
                indeg[j] -= 1
                if indeg[j] == 0:
                    q.append(j)
        if len(order) != len(self.comb):
            raise SystemExit("combinational loop, %d of %d ordered" % (len(order), len(self.comb)))
        self.order = order

        self.val = defaultdict(int)
        self.val[self.vdd] = 1
        self.val[self.vss] = 0
        self.q = {i: 0 for i in self.flop}

    def eval_comb(self, inputs):
        v = self.val
        for name, x in inputs.items():
            v[self.ports[name]] = x
        v[self.vdd] = 1
        v[self.vss] = 0
        for i in self.flop:
            it = self.insts[i]
            v[it["conns"]["Q"]] = self.q[i]
        for i in self.order:
            it = self.insts[i]
            c = {p: v[n] for p, n in it["conns"].items()}
            for p, x in COMB[it["cell"]](c).items():
                v[it["conns"][p]] = x

    def posedge(self):
        v = self.val
        nxt = {}
        for i in self.flop:
            it = self.insts[i]
            cn = it["conns"]
            k = it["cell"]
            if k == "dfrtp_2" and v[cn["RESET_B"]] == 0:
                nxt[i] = 0
            elif k == "dfstp_2" and v[cn["SET_B"]] == 0:
                nxt[i] = 1
            else:
                nxt[i] = v[cn["D"]] if "D" in cn else 0
        self.q = nxt

    def apply_async(self, inputs):
        """propagate async reset/set without a clock edge"""
        self.eval_comb(inputs)
        for _ in range(4):
            v = self.val
            changed = False
            for i in self.flop:
                it = self.insts[i]
                cn = it["conns"]
                k = it["cell"]
                new = None
                if k == "dfrtp_2" and v[cn["RESET_B"]] == 0:
                    new = 0
                elif k == "dfstp_2" and v[cn["SET_B"]] == 0:
                    new = 1
                if new is not None and self.q[i] != new:
                    self.q[i] = new
                    changed = True
            self.eval_comb(inputs)
            if not changed:
                break

    def out(self):
        v = self.val
        o = 0
        for b in range(8):
            o |= v[self.ports["O[%d]" % b]] << b
        return o, v[self.ports["success"]]


def run(bits, reset_cycles=4, tail=40, verbose=False):
    d = Design()
    # reset
    for _ in range(reset_cycles):
        d.apply_async({"clk": 0, "rst_n": 0, "enable": 0, "I": 0})
        d.posedge()
    trace = []
    for b in bits:
        d.apply_async({"clk": 0, "rst_n": 1, "enable": 1, "I": int(b)})
        d.posedge()
    for _ in range(tail):
        d.apply_async({"clk": 0, "rst_n": 1, "enable": 0, "I": 0})
        o, s = d.out()
        trace.append((o, s))
        d.posedge()
    return trace


if __name__ == "__main__":
    bits = sys.argv[1] if len(sys.argv) > 1 else "0" * 121
    tr = run(bits)
    txt = "".join(chr(o) for o, s in tr if 32 <= o < 127)
    print("output chars:", repr(txt))
    print("success high:", any(s for o, s in tr))
    print("raw:", [(o, s) for o, s in tr if o or s])
