# ASIC puzzle 2026 Jane Street
<img src="images/layout.png" width="50%">

<br>

## GDS file
First I checked the `puzzle.gds` file using KLayout 0.30.12 and I noticed several things:
- opening the Dysplay/Cells tab all instances had very specific names, such as `sky130_fd_sc_hd__dfrtp_2`, `sky130_fd_sc_hd__nand2_2`, etc...
- all input and output pin lable were present

This made me realize that the right path was to extract the netlist and not look for a pattern in the geometry.

### Cell Naming Convention

The standard cell `sky130_fd_sc_hd__dfrtp_2` can be broken down as follows:

| Field | Meaning |
|---|---|
| `sky130` | SkyWater SKY130 technology |
| `fd` | Foundry device |
| `sc` | Standard cell |
| `hd` | High density library |
| `__` | Separates the library name from the cell name |
| `dfrtp` | D flip flop with asynchronous reset and positive clock edge |
| `_2` | Drive strength 2 |

In other words, `sky130_fd_sc_hd__dfrtp_2` is a **high density SKY130 standard cell implementing a D flip flop with asynchronous reset, using drive strength 2**.

<br>

## VCD file
I decided to look at the `example_inputs.vcd`file using GTKWave:

- At first `rst_n` is low for a few clk cycle, then it goes high.
- Then `enable` goes high and stays high for a long window, while `I` changes with each clock stroke. Counting the clock strokes with enable high you find that it is 121 bits.
- When `enable` goes low again, O starts producing value: TRY AGAIN in ASCII code.
- `success` stays at 0: that's the signal you need to make 1.


So the protocol is: reset, then 121 cycles with high enable and one bit on I per cycle (first cycle = MSB) then low enable. The job is to find the 121 bits.

### Waveform:
![](images/tb1.png)
![](images/tb2.png)

<br>

## Extracting the netlist from the GDS

```
python3 extract.py puzzle.gds
```
What does it do:
- flattens the geometry of each routing layer (including paths)
- does a boolean OR per layer, so each resulting disjoint polygon is a single electric island
- each path cut joins, with union-find, the island below and the island above: this gives the threads (net)
- takes the pin labels inside each cell (text on li1, 67/5), transforms them into the top coordinates and locates them inside an island, obtaining the pin --> net binding
- reads the top ports and power supply
- write puzzle_netlist.v (Structural Verilog) and puzzle_netlist.json

