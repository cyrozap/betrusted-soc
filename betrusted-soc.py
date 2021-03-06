#!/usr/bin/env python3
# This variable defines all the external programs that this module
# relies on.  lxbuildenv reads this variable in order to ensure
# the build will finish without exiting due to missing third-party
# programs.

LX_DEPENDENCIES = ["riscv", "vivado"]

# Import lxbuildenv to integrate the deps/ directory
import lxbuildenv
import lxsocdoc

from random import SystemRandom
import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform, VivadoProgrammer

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.integration.doc import AutoDoc, ModuleDoc
from litex.soc.cores import spi_flash

from gateware import info
from gateware import sram_32
from gateware import memlcd
from gateware import spi
from gateware import messible
from gateware import i2c
from gateware import ticktimer

from gateware import spinor
from gateware import keyboard

_io = [
    # see main() for UART pins

    ("clk12", 0, Pins("R3"), IOStandard("LVCMOS18")),

    #("usbc_cc1", 0, Pins("C17"), IOStandard("LVCMOS33")), # analog
    #("usbc_cc2", 0, Pins("E16"), IOStandard("LVCMOS33")), # analog
    # ("vbus_div", 0, Pins("E12"), IOStandard("LVCMOS33")), # analog
    ("lpclk", 0, Pins("N15"), IOStandard("LVCMOS18")),  # wifi_lpclk

    # Power control signals
    ("power", 0,
        Subsignal("audio_on", Pins("G13"), IOStandard("LVCMOS33")),
        Subsignal("fpga_sys_on", Pins("N13"), IOStandard("LVCMOS18")),
        Subsignal("noisebias_on", Pins("A13"), IOStandard("LVCMOS33")),
        Subsignal("allow_up5k_n", Pins("U7"), IOStandard("LVCMOS18")),
        Subsignal("pwr_s0", Pins("U6"), IOStandard("LVCMOS18")),
        Subsignal("pwr_s1", Pins("L13"), IOStandard("LVCMOS18")),
        # Noise generator
        Subsignal("noise_on", Pins("P14", "R13"), IOStandard("LVCMOS18")),
    #    ("noise0", 0, Pins("B13"), IOStandard("LVCMOS33")), # these are analog
    #    ("noise1", 0, Pins("B14"), IOStandard("LVCMOS33")),
     ),

    # Audio interface
    ("au_clk1", 0, Pins("D14"), IOStandard("LVCMOS33")),
    ("au_clk2", 0, Pins("F14"), IOStandard("LVCMOS33")),
    ("au_mclk", 0, Pins("D18"), IOStandard("LVCMOS33")),
    ("au_sdi1", 0, Pins("D12"), IOStandard("LVCMOS33")),
    ("au_sdi2", 0, Pins("A15"), IOStandard("LVCMOS33")),
    ("au_sdo1", 0, Pins("C13"), IOStandard("LVCMOS33")),
    ("au_sync1", 0, Pins("B15"), IOStandard("LVCMOS33")),
    ("au_sync2", 0, Pins("B17"), IOStandard("LVCMOS33")),
#    ("ana_vn", 0, Pins("K9"), IOStandard("LVCMOS33")), # analog
#    ("ana_vp", 0, Pins("J10"), IOStandard("LVCMOS33")),

    # I2C1 bus -- to RTC and audio CODEC
    ("i2c", 0,
        Subsignal("scl", Pins("C14"), IOStandard("LVCMOS33")),
        Subsignal("sda", Pins("A14"), IOStandard("LVCMOS33")),
     ),
    # RTC interrupt
    ("rtc_irq", 0, Pins("N5"), IOStandard("LVCMOS18")),

    # COM interface to UP5K
    ("com", 0,
        Subsignal("csn", Pins("T15"), IOStandard("LVCMOS18")),
        Subsignal("miso", Pins("P16"), IOStandard("LVCMOS18")),
        Subsignal("mosi", Pins("N18"), IOStandard("LVCMOS18")),
        Subsignal("sclk", Pins("R16"), IOStandard("LVCMOS18")),
     ),
    ("com_irq", 0, Pins("M16"), IOStandard("LVCMOS18")),

    # Top-side internal FPC header
    ("gpio", 0, Pins("A16", "B16", "D16"), IOStandard("LVCMOS33"), Misc("SLEW=SLOW")), # B18 and D15 are used by the serial bridge

    # Keyboard scan matrix
    ("kbd", 0,
        # "key" 0-8 are rows, 9-18 are columns
        Subsignal("row", Pins("F15", "E17", "G17", "E14", "E15", "H15", "G15", "H14",
                              "H16"), IOStandard("LVCMOS33"), Misc("PULLDOWN True")),  # column scan with 1's, so PD to default 0
        Subsignal("col", Pins("H17", "E18", "F18", "G18", "E13", "H18", "F13",
                              "H13", "J13", "K13"), IOStandard("LVCMOS33")),
    ),

    # LCD interface
    ("lcd", 0,
        Subsignal("sclk", Pins("A17"), IOStandard("LVCMOS33"), Misc("SLEW=SLOW")),
        Subsignal("scs", Pins("C18"), IOStandard("LVCMOS33"), Misc("SLEW=SLOW")),
        Subsignal("si", Pins("D17"), IOStandard("LVCMOS33"), Misc("SLEW=SLOW")),
     ),

    # SD card (TF) interface
    ("sdcard", 0,
     Subsignal("data", Pins("J15 J14 K16 K14"), Misc("PULLUP True")),
     Subsignal("cmd", Pins("J16"), Misc("PULLUP True")),
     Subsignal("clk", Pins("G16")),
     IOStandard("LVCMOS33"), Misc("SLEW=SLOW")
     ),

    # SPI Flash
    ("spiflash_4x", 0,  # clock needs to be accessed through STARTUPE2
     Subsignal("cs_n", Pins("M13")),
     Subsignal("dq", Pins("K17", "K18", "L14", "M15")),
     IOStandard("LVCMOS18")
     ),
    ("spiflash_1x", 0,  # clock needs to be accessed through STARTUPE2
     Subsignal("cs_n", Pins("M13")),
     Subsignal("mosi", Pins("K17")),
     Subsignal("miso", Pins("K18")),
     Subsignal("wp", Pins("L14")), # provisional
     Subsignal("hold", Pins("M15")), # provisional
     IOStandard("LVCMOS18")
     ),
    ("spiflash_8x", 0,  # clock needs to be accessed through STARTUPE2
     Subsignal("cs_n", Pins("M13")),
     Subsignal("dq", Pins("K17", "K18", "L14", "M15", "L17", "L18", "M14", "N14")),
     Subsignal("dqs", Pins("R14")),
     Subsignal("ecsn", Pins("L16")),
     IOStandard("LVCMOS18")
     ),

    # SRAM
    ("sram", 0,
        Subsignal("adr", Pins(
            "V12 M5 P5 N4  V14 M3 R17 U15",
            "M4  L6 K3 R18 U16 K1 R5  T2",
            "U1  N1 L5 K2  M18 T6"),
            IOStandard("LVCMOS18")),
        Subsignal("ce_n", Pins("V5"), IOStandard("LVCMOS18"), Misc("PULLUP True")),
        Subsignal("oe_n", Pins("U12"), IOStandard("LVCMOS18"), Misc("PULLUP True")),
        Subsignal("we_n", Pins("K4"), IOStandard("LVCMOS18"), Misc("PULLUP True")),
        Subsignal("zz_n", Pins("V17"), IOStandard("LVCMOS18"), Misc("PULLUP True")),
        Subsignal("d", Pins(
            "M2  R4  P2  L4  L1  M1  R1  P1 "
            "U3  V2  V4  U2  N2  T1  K6  J6 "
            "V16 V15 U17 U18 P17 T18 P18 M17 "
            "N3  T4  V13 P15 T14 R15 T3  R7 "), IOStandard("LVCMOS18")),
        Subsignal("dm_n", Pins("V3 R2 T5 T13"), IOStandard("LVCMOS18")),
    ),
]

class Platform(XilinxPlatform):
    def __init__(self, toolchain="vivado", programmer="vivado", part="50"):
        part = "xc7s" + part + "-csga324-1il"
        XilinxPlatform.__init__(self, part, _io,
                                toolchain=toolchain)

        # NOTE: to do quad-SPI mode, the QE bit has to be set in the SPINOR status register
        # OpenOCD won't do this natively, have to find a work-around (like using iMPACT to set it once)
        self.add_platform_command(
            "set_property CONFIG_VOLTAGE 1.8 [current_design]")
        self.add_platform_command(
            "set_property CFGBVS VCCO [current_design]")
        self.add_platform_command(
            "set_property BITSTREAM.CONFIG.CONFIGRATE 66 [current_design]")
        self.add_platform_command(
            "set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 1 [current_design]")
        self.toolchain.bitstream_commands = [
            "set_property CONFIG_VOLTAGE 1.8 [current_design]",
            "set_property CFGBVS GND [current_design]",
            "set_property BITSTREAM.CONFIG.CONFIGRATE 66 [current_design]",
            "set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 1 [current_design]",
        ]
        self.toolchain.additional_commands = \
            ["write_cfgmem -verbose -force -format bin -interface spix1 -size 64 "
             "-loadbit \"up 0x0 {build_name}.bit\" -file {build_name}.bin"]
        self.programmer = programmer

    def create_programmer(self):
        if self.programmer == "vivado":
            return VivadoProgrammer(flash_part="n25q128-1.8v-spi-x1_x2_x4")
        else:
            raise ValueError("{} programmer is not supported"
                             .format(self.programmer))

    def do_finalize(self, fragment):
        XilinxPlatform.do_finalize(self, fragment)

slow_clock = False

class CRG(Module, AutoCSR):
    def __init__(self, platform):
        refclk_freq = 12e6

        clk12 = platform.request("clk12")
        rst = Signal()
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_spi = ClockDomain()
        self.clock_domains.cd_lpclk = ClockDomain()

        clk32khz = platform.request("lpclk")
        self.specials += [
            Instance("BUFG", i_I=clk32khz, o_O=self.cd_lpclk.clk)
        ]

        if slow_clock:
            self.specials += [
                Instance("BUFG", i_I=clk12, o_O=self.cd_sys.clk),
                AsyncResetSynchronizer(self.cd_sys, rst),
            ]

        else:
            # DRP
            self._mmcm_read = CSR()
            self._mmcm_write = CSR()
            self._mmcm_drdy = CSRStatus()
            self._mmcm_adr = CSRStorage(7)
            self._mmcm_dat_w = CSRStorage(16)
            self._mmcm_dat_r = CSRStatus(16)

            pll_locked = Signal()
            pll_fb = Signal()
            pll_sys = Signal()
            pll_spiclk = Signal()
            clk12_distbuf = Signal()

            self.specials += [
                Instance("BUFG", i_I=clk12, o_O=clk12_distbuf),
                # this allows PLLs/MMCMEs to be placed anywhere and reference the input clock
            ]

            pll_fb_bufg = Signal()
            mmcm_drdy = Signal()
            self.warm_reset = Signal()
            self.specials += [
                Instance("MMCME2_ADV",
                         p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,
                         p_BANDWIDTH="OPTIMIZED",

                         # VCO @ 600MHz  (600-1200 range for -1LI)
                         p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=(1 / refclk_freq) * 1e9,
                         p_CLKFBOUT_MULT_F=50.0, p_DIVCLK_DIVIDE=1,
                         i_CLKIN1=clk12_distbuf, i_CLKFBIN=pll_fb_bufg, o_CLKFBOUT=pll_fb,

                         # 100 MHz - sysclk
                         p_CLKOUT0_DIVIDE_F=6.0, p_CLKOUT0_PHASE=0.0,
                         o_CLKOUT0=pll_sys,

                         # 20 MHz - spiclk
                         p_CLKOUT1_DIVIDE=30, p_CLKOUT1_PHASE=0,
                         o_CLKOUT1=pll_spiclk,

                         # DRP
                         i_DCLK=ClockSignal(),
                         i_DWE=self._mmcm_write.re,
                         i_DEN=self._mmcm_read.re | self._mmcm_write.re,
                         o_DRDY=mmcm_drdy,
                         i_DADDR=self._mmcm_adr.storage,
                         i_DI=self._mmcm_dat_w.storage,
                         o_DO=self._mmcm_dat_r.status,

                         # Warm reset
                         i_RST=self.warm_reset,
                         ),

                # feedback delay compensation buffers
                Instance("BUFG", i_I=pll_fb, o_O=pll_fb_bufg),

                # global distribution buffers
                Instance("BUFG", i_I=pll_sys, o_O=self.cd_sys.clk),
                Instance("BUFG", i_I=pll_spiclk, o_O=self.cd_spi.clk),

                AsyncResetSynchronizer(self.cd_sys, rst | ~pll_locked),
                AsyncResetSynchronizer(self.cd_spi, rst | ~pll_locked),
            ]
            self.sync += [
                If(self._mmcm_read.re | self._mmcm_write.re,
                   self._mmcm_drdy.status.eq(0)
                   ).Elif(mmcm_drdy,
                          self._mmcm_drdy.status.eq(1)
                          )
            ]

class WarmBoot(Module, AutoCSR):
    def __init__(self, parent, reset_vector=0):
        self.ctrl = CSRStorage(size=8)
        self.addr = CSRStorage(size=32, reset=reset_vector)
        self.do_reset = Signal()
        self.comb += [
            # "Reset Key" is 0xac (0b101011xx)
            self.do_reset.eq(self.ctrl.storage[2] & self.ctrl.storage[3] & ~self.ctrl.storage[4]
                      & self.ctrl.storage[5] & ~self.ctrl.storage[6] & self.ctrl.storage[7])
        ]

class BtEvents(Module, AutoCSR, AutoDoc):
    def __init__(self, com, rtc):
        self.submodules.ev = EventManager()
        self.ev.com_int = EventSourcePulse()  # rising edge triggered
        self.ev.rtc_int = EventSourceProcess() # falling edge triggered
        self.ev.finalize()

        com_int = Signal()
        rtc_int = Signal()
        self.specials += MultiReg(com, com_int)
        self.specials += MultiReg(rtc, rtc_int)
        self.comb += self.ev.com_int.trigger.eq(com_int)
        self.comb += self.ev.rtc_int.trigger.eq(rtc_int)

class BtPower(Module, AutoCSR, AutoDoc):
    def __init__(self, pads):
        self.intro = ModuleDoc("""BtPower - power control pins
        """)

        self.power = CSRStorage(8, fields=[
            CSRField("audio", description="Write `1` to power on the audio subsystem"),
            CSRField("self", description="Writing `1` forces self power-on (overrides the EC's ability to power me down)", reset=1),
            CSRField("ec_snoop", description="Writing `1` allows the insecure EC to snoop a couple keyboard pads for wakeup key sequence recognition"),
            CSRField("state", size=2, description="Current SoC power state. 0x=off or not ready, 10=on and safe to shutdown, 11=on and not safe to shut down, resets to 01 to allow extSRAM access immediately during init", reset=1),
            CSRField("noisebias", description="Writing `1` enables the primary bias supply for the noise generator"),
            CSRField("noise", size=2, description="Controls which of two noise channels are active; all combos valid. noisebias must be on first.")
        ])

        self.comb += [
            pads.audio_on.eq(self.power.fields.audio),
            pads.fpga_sys_on.eq(self.power.fields.self),
            pads.allow_up5k_n.eq(~self.power.fields.ec_snoop), # this signal automatically enables snoop when SoC is powered down
            pads.pwr_s0.eq(self.power.fields.state[0] & ~ResetSignal()),  # ensure SRAM isolation during reset (CE & ZZ = 1 by pull-ups)
            pads.pwr_s1.eq(self.power.fields.state[1]),
            pads.noisebias_on.eq(self.power.fields.noisebias),
            pads.noise_on.eq(self.power.fields.noise),
        ]

class BtGpio(Module, AutoDoc, AutoCSR):
    def __init__(self, pads):
        self.intro = ModuleDoc("""BtGpio - GPIO interface for betrusted""")

        gpio_in = Signal(pads.nbits)
        gpio_out = Signal(pads.nbits)
        gpio_oe = Signal(pads.nbits)

        for g in range(0, pads.nbits):
            gpio_ts = TSTriple(1)
            self.specials += gpio_ts.get_tristate(pads[g])
            self.comb += [
                gpio_ts.oe.eq(gpio_oe[g]),
                gpio_ts.o.eq(gpio_out[g]),
                gpio_in[g].eq(gpio_ts.i),
            ]

        self.output = CSRStorage(pads.nbits, name="output", description="Values to appear on GPIO when respective `drive` bit is asserted")
        self.input = CSRStatus(pads.nbits, name="input", description="Value measured on the respective GPIO pin")
        self.drive = CSRStorage(pads.nbits, name="drive", description="When a bit is set to `1`, the respective pad drives its value out")
        self.intena = CSRStatus(pads.nbits, name="intena", description="Enable interrupts when a respective bit is set")
        self.intpol = CSRStatus(pads.nbits, name="intpol", description="When a bit is `1`, falling-edges cause interrupts. Otherwise, rising edges cause interrupts.")

        self.specials += MultiReg(gpio_in, self.input.status)
        self.comb += [
            gpio_out.eq(self.output.storage),
            gpio_oe.eq(self.drive.storage),
        ]

        self.submodules.ev = EventManager()

        for i in range(0, pads.nbits):
            setattr(self.ev, "gpioint" + str(i), EventSourcePulse() ) # pulse => rising edge

        self.ev.finalize()

        for i in range(0, pads.nbits):
            # pull from input.status because it's after the MultiReg synchronizer
            self.comb += getattr(self.ev, "gpioint" + str(i)).trigger.eq(self.input.status[i] ^ self.intpol.status[i])
            # note that if you change the polarity on the interrupt it could trigger an interrupt

class BtSeed(Module, AutoDoc, AutoCSR):
    def __init__(self, reproduceable=False):
        self.intro = ModuleDoc("""Place and route seed. Set to a fixed number for reproduceable builds.
        Use a random number or your own number if you are paranoid about hardware implants that target
        fixed locations within the FPGA.""")

        rng = SystemRandom()
        if reproduceable:
            self.seed = CSRStatus(64, name="seed", description="Seed used for the build", reset="4") # chosen by fair dice roll. guaranteed to be random.
        else:
            self.seed = CSRStatus(64, name="seed", description="Seed used for the build", reset=rng.getrandbits(64))




boot_offset = 0x500000 # enough space to hold 2x FPGA bitstreams before the firmware start
bios_size = 0x8000
# 128 MB (1024 Mb), but reduce to 64Mbit for bring-up because we don't have extended page addressing implemented yet
SPI_FLASH_SIZE = 16 * 1024 * 1024

class BaseSoC(SoCCore):
    # addresses starting with 0xB, 0xE, and 0xF are I/O and not cacheable
    SoCCore.mem_map = {
        "rom": 0x00000000, # required to keep litex happy
        "sram": 0x10000000,
        "spiflash": 0x20000000,
        "sram_ext": 0x40000000,
        "memlcd": 0xB0000000,
        "csr": 0xF0000000,
    }

    def __init__(self, platform, spiflash="spiflash_1x", **kwargs):
        if slow_clock:
            clk_freq = int(12e6)
        else:
            clk_freq = int(100e6)

        # CPU cluster
        ## For dev work, we're booting from SPI directly. However, for enhanced security
        ## we will eventually want to move to a bitstream-ROM based bootloder that does
        ## a signature verification of the external SPI code before running it. The theory is that
        ## a user will burn a random AES key into their FPGA and encrypt their bitstream to their
        ## unique AES key, creating a root of trust that offers a defense against trivial patch attacks.
        SoCCore.__init__(self, platform, clk_freq,
                         integrated_rom_size=0,
                         integrated_sram_size=0x20000,
                         ident="betrusted.io LiteX Base SoC",
                         cpu_type="vexriscv",
#                         cpu_variant="linux+debug",  # this core doesn't work, but left for jogging my memory later on if I need to try it
                         **kwargs)
        self.cpu.use_external_variant("gateware/cpu/VexRiscv_BetrustedSoC_Debug.v")
        self.cpu.add_debug()
        self.add_memory_region("rom", 0, 0) # Required to keep litex happy
        kwargs['cpu_reset_address']=self.mem_map["spiflash"]+boot_offset
        self.submodules.reboot = WarmBoot(self, reset_vector=kwargs['cpu_reset_address'])
        self.add_csr("reboot")
        warm_reset = Signal()
        self.comb += warm_reset.eq(self.reboot.do_reset)
        self.cpu.cpu_params.update(
            i_externalResetVector=self.reboot.addr.storage,
        )
        # Debug cluster
        from litex.soc.cores.uart import UARTWishboneBridge
        self.submodules.uart_bridge = UARTWishboneBridge(platform.request("debug"), clk_freq, baudrate=115200)
        self.add_wb_master(self.uart_bridge.wishbone)
        self.register_mem("vexriscv_debug", 0xe00f0000, self.cpu.debug_bus, 0x100)

        # clockgen cluster
        self.submodules.crg = CRG(platform)
        self.add_csr("crg")
        self.platform.add_period_constraint(self.crg.cd_sys.clk, 1e9/clk_freq)
        self.comb += self.crg.warm_reset.eq(warm_reset)
        self.platform.add_platform_command(
            "create_clock -name clk12 -period 83.3333 [get_nets clk12]")
        self.platform.add_platform_command(
            "create_clock -name sys_clk -period 10.0 [get_nets sys_clk]")
        self.platform.add_platform_command(
            "create_clock -name spi_clk -period 50.0 [get_nets spi_clk]")
        self.platform.add_platform_command(
            "create_clock -name lpclk -period 30517.5781 [get_nets lpclk]") # 32768 Hz in ns
        self.platform.add_platform_command(
            "create_generated_clock -name sys_clk -source [get_pins MMCME2_ADV/CLKIN1] -multiply_by 50 -divide_by 6 -add -master_clock clk12 [get_pins MMCME2_ADV/CLKOUT0]"
        )

        self.submodules.info = info.Info(platform, self.__class__.__name__)
        self.add_csr("info")
        self.platform.add_platform_command('create_generated_clock -name dna_cnt -source [get_pins {{info_dna_cnt_reg[0]/Q}}] -divide_by 2 [get_pins {{DNA_PORT/CLK}}]')

        # external SRAM
        # Note that page_rd_timing=2 works, but is a slight overclock on RAM. Cache fill time goes from 436ns to 368ns for 8 words.
        self.submodules.sram_ext = sram_32.Sram32(platform.request("sram"), rd_timing=7, wr_timing=6, page_rd_timing=3)  # this works with 2:nbits page length with Rust firmware...
        #self.submodules.sram_ext = sram_32.Sram32(platform.request("sram"), rd_timing=7, wr_timing=6, page_rd_timing=5)  # this worked with 3:nbits page length in C firmware
        self.add_csr("sram_ext")
        self.register_mem("sram_ext", self.mem_map["sram_ext"],
                  self.sram_ext.bus, size=0x1000000)
        # constraint so a total of one extra clock period is consumed in routing delays (split 5/5 evenly on in and out)
        self.platform.add_platform_command("set_input_delay -clock [get_clocks sys_clk] -min -add_delay 5.0 [get_ports {{sram_d[*]}}]")
        self.platform.add_platform_command("set_input_delay -clock [get_clocks sys_clk] -max -add_delay 5.0 [get_ports {{sram_d[*]}}]")
        self.platform.add_platform_command("set_output_delay -clock [get_clocks sys_clk] -min -add_delay 0.0 [get_ports {{sram_adr[*] sram_d[*] sram_ce_n sram_oe_n sram_we_n sram_zz_n sram_dm_n[*]}}]")
        self.platform.add_platform_command("set_output_delay -clock [get_clocks sys_clk] -max -add_delay 4.5 [get_ports {{sram_adr[*] sram_d[*] sram_ce_n sram_oe_n sram_we_n sram_zz_n sram_dm_n[*]}}]")
        # ODDR falling edge ignore
        self.platform.add_platform_command("set_false_path -fall_from [get_clocks sys_clk] -through [get_ports {{sram_d[*] sram_adr[*] sram_ce_n sram_oe_n sram_we_n sram_zz_n sram_dm_n[*]}}]")
        self.platform.add_platform_command("set_false_path -fall_to [get_clocks sys_clk] -through [get_ports {{sram_d[*]}}]")
        self.platform.add_platform_command("set_false_path -fall_from [get_clocks sys_clk] -through [get_nets sram_ext_load]")
        self.platform.add_platform_command("set_false_path -fall_to [get_clocks sys_clk] -through [get_nets sram_ext_load]")
        self.platform.add_platform_command("set_false_path -rise_from [get_clocks sys_clk] -fall_to [get_clocks sys_clk]")  # sort of a big hammer but should be OK
        # reset ignore
        self.platform.add_platform_command("set_false_path -through [get_nets sys_rst]")
        # relax OE driver constraint (it's OK if it is a bit late, and it's an async path from fabric to output so it will be late)
        self.platform.add_platform_command("set_multicycle_path 2 -setup -through [get_pins sram_ext_sync_oe_n_reg/Q]")
        self.platform.add_platform_command("set_multicycle_path 1 -hold -through [get_pins sram_ext_sync_oe_n_reg/Q]")

        # LCD interface
        self.submodules.memlcd = memlcd.Memlcd(platform.request("lcd"))
        self.add_csr("memlcd")
        self.register_mem("memlcd", self.mem_map["memlcd"], self.memlcd.bus, size=self.memlcd.fb_depth*4)

        # COM SPI interface
        self.submodules.com = spi.SpiMaster(platform.request("com"))
        self.add_csr("com")
        # 20.83ns = 1/2 of 24MHz clock, we are doing falling-to-rising timing
        # up5k tsu = -0.5ns, th = 5.55ns, tpdmax = 10ns
        # in reality, we are measuring a Tpd from the UP5K of 17ns. Routed input delay is ~3.9ns, which means
        # the fastest clock period supported would be 23.9MHz - just shy of 24MHz, with no margin to spare.
        # slow down clock period of SPI to 20MHz, this gives us about a 4ns margin for setup for PVT variation
        self.platform.add_platform_command("set_input_delay -clock [get_clocks spi_clk] -min -add_delay 0.5 [get_ports {{com_miso}}]") # could be as low as -0.5ns but why not
        self.platform.add_platform_command("set_input_delay -clock [get_clocks spi_clk] -max -add_delay 17.5 [get_ports {{com_miso}}]")
        self.platform.add_platform_command("set_output_delay -clock [get_clocks spi_clk] -min -add_delay 6.0 [get_ports {{com_mosi com_csn}}]")
        self.platform.add_platform_command("set_output_delay -clock [get_clocks spi_clk] -max -add_delay 16.0 [get_ports {{com_mosi com_csn}}]")  # could be as large as 21ns but why not
        # cross domain clocking is handled with explicit software barrires, or with multiregs
        self.platform.add_false_path_constraints(self.crg.cd_sys.clk, self.crg.cd_spi.clk)
        self.platform.add_false_path_constraints(self.crg.cd_spi.clk, self.crg.cd_sys.clk)

        # add I2C interface
        self.submodules.i2c = i2c.RTLI2C(platform, platform.request("i2c", 0))
        self.add_csr("i2c")
        self.add_interrupt("i2c")

        # event generation for I2C and COM
        self.submodules.btevents = BtEvents(platform.request("com_irq", 0), platform.request("rtc_irq", 0))
        self.add_csr("btevents")
        self.add_interrupt("btevents")

        # add messible for debug
        self.submodules.messible = messible.Messible()
        self.add_csr("messible")

        # Tick timer
        self.submodules.ticktimer = ticktimer.TickTimer(clk_freq / 1000)
        self.add_csr("ticktimer")

        # Power control pins
        self.submodules.power = BtPower(platform.request("power"))
        self.add_csr("power")

        # SPI flash controller
        spi_pads = platform.request("spiflash_1x")
        self.submodules.spinor = spinor.SpiNor(platform, spi_pads, size=SPI_FLASH_SIZE)
        self.register_mem("spiflash", self.mem_map["spiflash"],
            self.spinor.bus, size=SPI_FLASH_SIZE)
        self.add_csr("spinor")

        # Keyboard module
        self.submodules.keyboard = ClockDomainsRenamer(cd_remapping={"kbd":"lpclk"})(keyboard.KeyScan(platform.request("kbd")))
        self.add_csr("keyboard")
        self.add_interrupt("keyboard")

        # GPIO module
        self.submodules.gpio = BtGpio(platform.request("gpio"))
        self.add_csr("gpio")
        self.add_interrupt("gpio")

        # Build seed
        self.submodules.seed = BtSeed()
        self.add_csr("seed")

        ## TODO: XADC, audio, wide-width/fast SPINOR, sdcard
"""
        # this is how to force a block in a given location
        platform.toolchain.attr_translate["icap0"] = ("LOC", "ICAP_X0Y0")
        platform.toolchain.attr_translate["KEEP"] = ("KEEP", "TRUE")
        platform.toolchain.attr_translate["DONT_TOUCH"] = ("DONT_TOUCH", "TRUE")
        self.specials += [
            Instance("ICAPE2",
                     i_I=0,
                     i_RDWRB=1,
                     attr={"KEEP", "DONT_TOUCH", "icap0"}
                     )
        ]

        # turns into the following verilog:
(* DONT_TOUCH = "TRUE", KEEP = "TRUE", LOC = "ICAP_X0Y0" *) ICAPE2 ICAPE2(
        .I(1'd0),
        .RDWRB(1'd1)
);

"""


def main():
    global _io

    if os.environ['PYTHONHASHSEED'] != "1":
        print( "PYTHONHASHEED must be set to 1 for consistent validation results. Failing to set this results in non-deterministic compilation results")
        exit()

    parser = argparse.ArgumentParser(description="Build the Betrusted SoC")
    parser.add_argument(
        "-D", "--document-only", default=False, action="store_true", help="Build docs only"
    )
    parser.add_argument(
        "-u", "--uart-swap", default=False, action="store_true", help="swap UART pins (GDB debug bridge <-> console)"
    )

    args = parser.parse_args()
    compile_gateware = True
    compile_software = False

    if args.document_only:
        compile_gateware = False
        compile_software = False

    if args.uart_swap:
        _io += [
            ("serial", 0,  # wired to the RPi
             Subsignal("tx", Pins("V6")),
             Subsignal("rx", Pins("V7")),
             IOStandard("LVCMOS18"),
             ),

            ("debug", 0,   # wired to the internal flex
             Subsignal("tx", Pins("B18")),  # debug0 breakout
             Subsignal("rx", Pins("D15")),  # debug1
             IOStandard("LVCMOS33"),
             ),
        ]
    else:  # default to GDB bridge going to the Pi
        _io += [
            ("debug", 0,   # wired to the Rpi
             Subsignal("tx", Pins("V6")),
             Subsignal("rx", Pins("V7")),
             IOStandard("LVCMOS18"),
             ),

            ("serial", 0,  # wired to the internal flex
             Subsignal("tx", Pins("B18")),  # debug0 breakout
             Subsignal("rx", Pins("D15")),  # debug1
             IOStandard("LVCMOS33"),
             ),
        ]

    platform = Platform()
    soc = BaseSoC(platform)
    builder = Builder(soc, output_dir="build", csr_csv="test/csr.csv", compile_software=compile_software, compile_gateware=compile_gateware)
    vns = builder.build()
    soc.do_exit(vns)
    lxsocdoc.generate_docs(soc, "build/documentation", note_pulses=True)
    lxsocdoc.generate_svd(soc, "build/software", name="Betrusted SoC", description="Primary UI Core for Betrusted", filename="soc.svd", vendor="Betrusted-IO")

if __name__ == "__main__":
    main()
