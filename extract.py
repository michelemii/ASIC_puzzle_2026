#!/usr/bin/env python3
import gdstk
import math
import sys
import time
import json
from collections import defaultdict, Counter

GDS_PATH = sys.argv[1] if len(sys.argv) > 1 else "C:/.../puzzle.gds" # path to the GDS file
TOP_NAME = "puzzle"
OUT_V = "C:/.../puzzle_netlist.v" # path to the output Verilog file
OUT_JSON = "C:/.../puzzle_netlist.json" # path to the output JSON file

# routing layers and cut layers used in the puzzle
ROUTE = [(67, 20), (68, 20), (69, 20), (70, 20), (71, 20), (72, 20)]
CUTS = {
    (67, 44): ((67, 20), (68, 20)),
    (68, 44): ((68, 20), (69, 20)),
    (69, 44): ((69, 20), (70, 20)),
    (70, 44): ((70, 20), (71, 20)),
    (71, 44): ((71, 20), (72, 20)),
}
LI = (67, 20)
MET1 = (68, 20)
MET3 = (70, 20)
LABEL_LI = (67, 5)
LABEL_MET1 = (68, 5)
LABEL_MET3 = (70, 5)


def log(*a):
    print("[%7.1fs]" % (time.time() - T0), *a, flush=True)


T0 = time.time()


# union find
class DSU:
    def __init__(self):
        self.p = {}

    def find(self, x):
        p = self.p
        if x not in p:
            p[x] = x
            return x
        r = x
        while p[r] != r:
            r = p[r]
        while p[x] != r:
            p[x], x = r, p[x]
        return r

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra
        return ra


# spatial index
class Grid:
    """bucket index over polygon bounding boxes for fast point location"""

    def __init__(self, polys, cell=4.0):
        self.cell = cell
        self.polys = polys
        self.bb = []
        self.buckets = defaultdict(list)
        for i, p in enumerate(polys):
            (x0, y0), (x1, y1) = p.bounding_box()
            self.bb.append((x0, y0, x1, y1))
            for gx in range(int(math.floor(x0 / cell)), int(math.floor(x1 / cell)) + 1):
                for gy in range(int(math.floor(y0 / cell)), int(math.floor(y1 / cell)) + 1):
                    self.buckets[(gx, gy)].append(i)

    def locate(self, x, y):
        """index of the polygon containing (x,y) or None"""
        c = self.cell
        cand = self.buckets.get((int(math.floor(x / c)), int(math.floor(y / c))))
        if not cand:
            return None
        hits = []
        for i in cand:
            x0, y0, x1, y1 = self.bb[i]
            if x0 - 1e-9 <= x <= x1 + 1e-9 and y0 - 1e-9 <= y <= y1 + 1e-9:
                hits.append(i)
        if not hits:
            return None
        if len(hits) == 1 and gdstk.inside([(x, y)], [self.polys[hits[0]]])[0]:
            return hits[0]
        for i in hits:
            if gdstk.inside([(x, y)], [self.polys[i]])[0]:
                return i
        # point may sit exactly on an edge
        for dx, dy in ((5e-4, 0), (-5e-4, 0), (0, 5e-4), (0, -5e-4)):
            for i in hits:
                if gdstk.inside([(x + dx, y + dy)], [self.polys[i]])[0]:
                    return i
        return None


# transform
def make_xf(ref):
    ox, oy = ref.origin
    mag = ref.magnification if ref.magnification else 1.0
    ang = ref.rotation if ref.rotation else 0.0
    ca, sa = math.cos(ang), math.sin(ang)
    refl = bool(ref.x_reflection)

    def f(pt):
        x, y = pt[0], pt[1]
        if refl:
            y = -y
        x *= mag
        y *= mag
        return (x * ca - y * sa + ox, x * sa + y * ca + oy)

    return f


# sky130 db
# pin direction table for every cell family used by the puzzle
OUTPUT_PINS = {"X", "Y", "Q", "Q_N", "HI", "LO", "COUT", "SUM"}
IGNORE_PINS = {"VPWR", "VGND", "VPB", "VNB", "VNB1", "VPB1", "DIODE"}


def main():
    lib = gdstk.read_gds(GDS_PATH)
    cells = {c.name: c for c in lib.cells}
    top = cells[TOP_NAME]
    log("loaded %s, %d cells, %d refs" % (GDS_PATH, len(cells), len(top.references)))

    # 1. flatten routing geometry, one merged set per layer
    islands = {}
    grids = {}
    for ld in ROUTE:
        raw = top.get_polygons(
            apply_repetitions=True, include_paths=True, depth=None,
            layer=ld[0], datatype=ld[1]
        )
        merged = gdstk.boolean(raw, [], "or", precision=1e-4) if raw else []
        islands[ld] = merged
        grids[ld] = Grid(merged)
        log("layer %d/%d: %6d shapes -> %5d islands" % (ld[0], ld[1], len(raw), len(merged)))

    # 2. vias union islands across adjacent layers
    dsu = DSU()
    for ld in ROUTE:
        for i in range(len(islands[ld])):
            dsu.find((ld, i))

    for cut, (lo, hi) in CUTS.items():
        cuts = top.get_polygons(
            apply_repetitions=True, include_paths=True, depth=None,
            layer=cut[0], datatype=cut[1]
        )
        nlink = nmiss = 0
        for c in cuts:
            pts = c.points
            cx = float(sum(p[0] for p in pts)) / len(pts)
            cy = float(sum(p[1] for p in pts)) / len(pts)
            a = grids[lo].locate(cx, cy)
            b = grids[hi].locate(cx, cy)
            if a is None or b is None:
                nmiss += 1
                continue
            dsu.union((lo, a), (hi, b))
            nlink += 1
        log("cut %d/%d: %5d cuts, %5d linked, %d unresolved" % (cut[0], cut[1], len(cuts), nlink, nmiss))

    # 3. net ids
    net_of = {}
    for ld in ROUTE:
        for i in range(len(islands[ld])):
            net_of[(ld, i)] = dsu.find((ld, i))
    roots = sorted(set(net_of.values()), key=lambda r: (r[0], r[1]))
    net_id = {r: i for i, r in enumerate(roots)}
    log("total nets: %d" % len(net_id))

    def net_at(ld, x, y):
        i = grids[ld].locate(x, y)
        if i is None:
            return None
        return net_id[dsu.find((ld, i))]

    # 4. instances and pins
    insts = []
    unresolved = Counter()
    for ridx, ref in enumerate(top.references):
        cname = ref.cell.name
        if not cname.startswith("sky130_fd_sc_hd__"):
            continue
        kind = cname[len("sky130_fd_sc_hd__"):]
        if kind.startswith(("tapvpwrvgnd", "decap", "fill", "diode")):
            continue
        f = make_xf(ref)
        conns = {}
        for lab in ref.cell.labels:
            if (lab.layer, lab.texttype) == LABEL_LI:
                nm = lab.text
                if nm in IGNORE_PINS or nm in conns:
                    continue
                x, y = f(lab.origin)
                n = net_at(LI, x, y)
                if n is None:
                    unresolved[(kind, nm)] += 1
                else:
                    conns[nm] = n
        insts.append({"idx": ridx, "cell": kind, "origin": list(ref.origin), "conns": conns})
    log("instances: %d, unresolved pins: %d" % (len(insts), sum(unresolved.values())))
    for k, v in unresolved.most_common(20):
        log("   UNRESOLVED", k, v)

    # 5. top ports
    ports = {}
    for lab in top.labels:
        if (lab.layer, lab.texttype) == LABEL_MET3:
            n = net_at(MET3, lab.origin[0], lab.origin[1])
            if n is None:
                for ld in ROUTE:
                    n = net_at(ld, lab.origin[0], lab.origin[1])
                    if n is not None:
                        break
            ports[lab.text] = n
            log("port %-10s -> net %s" % (lab.text, n))

    # 6. power nets, found through the VPWR / VGND labels of the cells
    pwr = Counter()
    gnd = Counter()
    for ref in top.references:
        if not ref.cell.name.startswith("sky130_fd_sc_hd__"):
            continue
        f = make_xf(ref)
        for lab in ref.cell.labels:
            if (lab.layer, lab.texttype) == LABEL_MET1 and lab.text in ("VPWR", "VGND"):
                x, y = f(lab.origin)
                n = net_at(MET1, x, y)
                if n is not None:
                    (pwr if lab.text == "VPWR" else gnd)[n] += 1
    vdd = pwr.most_common(1)[0][0] if pwr else None
    vss = gnd.most_common(1)[0][0] if gnd else None
    log("VPWR net %s (%d taps), VGND net %s (%d taps)" % (vdd, pwr[vdd], vss, gnd[vss]))
    if len(pwr) > 1:
        log("WARNING: VPWR resolves to several nets", pwr.most_common(5))
    if len(gnd) > 1:
        log("WARNING: VGND resolves to several nets", gnd.most_common(5))

    # 7. report
    fan = defaultdict(list)
    for i, it in enumerate(insts):
        for pin, n in it["conns"].items():
            fan[n].append((i, pin))
    drivers = defaultdict(list)
    for i, it in enumerate(insts):
        for pin, n in it["conns"].items():
            if pin in OUTPUT_PINS:
                drivers[n].append((i, pin))
    multi = {n: d for n, d in drivers.items() if len(d) > 1}
    log("nets with >1 driver: %d" % len(multi))
    for n, d in list(multi.items())[:10]:
        log("   net %d driven by %s" % (n, [(insts[i]['cell'], p) for i, p in d]))
    undriven = [n for n in fan if n not in drivers and n not in (vdd, vss) and n not in ports.values()]
    log("undriven signal nets: %d" % len(undriven))

    # 8. Verilog
    import os
    os.makedirs(os.path.dirname(OUT_V), exist_ok=True)
    name = {}
    for p, n in ports.items():
        if n is not None:
            name[n] = p.replace("[", "_").replace("]", "")
    if vdd is not None:
        name[vdd] = "VPWR"
    if vss is not None:
        name[vss] = "VGND"
    for n in sorted(fan):
        name.setdefault(n, "n%d" % n)

    lines = []
    lines.append("// extracted from %s" % GDS_PATH)
    lines.append("module puzzle (clk, rst_n, enable, I, O, success);")
    lines.append("  input clk, rst_n, enable, I;")
    lines.append("  output [7:0] O;")
    lines.append("  output success;")
    wires = sorted(set(name[n] for n in fan) - {"clk", "rst_n", "enable", "I", "success"} - {"O_%d" % i for i in range(8)})
    for w in wires:
        lines.append("  wire %s;" % w)
    lines.append("  assign O = {O_7,O_6,O_5,O_4,O_3,O_2,O_1,O_0};")
    lines.append("  supply1 VPWR;")
    lines.append("  supply0 VGND;")
    for i, it in enumerate(insts):
        cs = ", ".join(".%s(%s)" % (p, name.get(n, "n%d" % n)) for p, n in sorted(it["conns"].items()))
        lines.append("  sky130_fd_sc_hd__%s u%d (%s);" % (it["cell"], i, cs))
    lines.append("endmodule")
    open(OUT_V, "w").write("\n".join(lines) + "\n")
    log("wrote %s" % OUT_V)

    json.dump(
        {"instances": insts, "ports": ports, "vdd": vdd, "vss": vss, "n_nets": len(net_id)},
        open(OUT_JSON, "w"),
    )
    log("wrote %s" % OUT_JSON)

    log("cell histogram:")
    for k, v in Counter(i["cell"] for i in insts).most_common():
        log("   %-24s %d" % (k, v))


if __name__ == "__main__":
    main()
