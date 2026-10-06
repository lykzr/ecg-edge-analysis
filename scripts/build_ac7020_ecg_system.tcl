# 一次性构建 AC7020 + Zynq PS7 + ECG AXI-Lite 外设的 Block Design。
# 在 Vivado 中打开 ecg_edge 工程后，从 Tcl Console 执行本脚本。
# 脚本只准备工程和生成 Block Design 输出文件，不会启动综合、生成 bitstream 或烧录。

proc require_one {objects description} {
    if {[llength $objects] != 1} {
        error "${description} 应当恰好有一个，当前找到 [llength $objects] 个。"
    }
    return [lindex $objects 0]
}

proc connect_if_free {source_pin destination_pin description} {
    set source_net [get_bd_nets -quiet -of_objects $source_pin]
    set destination_net [get_bd_nets -quiet -of_objects $destination_pin]
    if {[llength $source_net] && [llength $destination_net]} {
        if {$source_net ne $destination_net} {
            error "${description} 两端已经接在不同网络上，请检查 Block Design。"
        }
        return
    }
    if {[llength $source_net]} {
        connect_bd_net $source_net $destination_pin
    } elseif {![llength $destination_net]} {
        connect_bd_net $source_pin $destination_pin
    }
}

if {[current_project -quiet] eq ""} {
    error "请先在 Vivado 中打开 ecg_edge 工程。"
}

set project_root [file normalize [file join [get_property DIRECTORY [current_project]] .. ..]]
set rtl_detector [file join $project_root rtl ecg_qrs_detector.sv]
set rtl_axi [file join $project_root rtl ecg_qrs_axi_lite.sv]
foreach rtl_file [list $rtl_detector $rtl_axi] {
    if {![file isfile $rtl_file]} {
        error "找不到 RTL 文件：$rtl_file"
    }
    if {![llength [get_files -quiet $rtl_file]]} {
        add_files -norecurse $rtl_file
    }
    set_property file_type SystemVerilog [get_files $rtl_file]
}
update_compile_order -fileset sources_1

set current_part [get_property PART [current_project]]
if {![string match -nocase "xc7z020clg400-2" $current_part]} {
    error "当前器件为 $current_part；AC7020 核心板应选择 xc7z020clg400-2。"
}
# AC7020 没有安装在本机 Vivado 的板级仓库中，使用器件型号和手册参数配置。
catch {set_property BOARD_PART {} [current_project]}

set bd_file [require_one [get_files -quiet -filter {NAME =~ *ecg_system.bd}] "ecg_system.bd"]
if {[current_bd_design -quiet] ne "ecg_system"} {
    open_bd_design $bd_file
}
if {[current_bd_design -quiet] ne "ecg_system"} {
    error "未能打开 ecg_system Block Design。"
}

set ps_cell [require_one [get_bd_cells -quiet processing_system7_0] "processing_system7_0"]
# AC7020：PS 输入时钟 33.333 MHz、32 位 DDR3、533.333 MHz、UART1 在 MIO48/49。
# 启用 100 MHz FCLK0 作为 AXI 时钟，并启用 PS 的 M_AXI_GP0 主接口。
set_property -dict [list \
    CONFIG.PCW_CRYSTAL_PERIPHERAL_FREQMHZ {33.333333} \
    CONFIG.PCW_PRESET_BANK0_VOLTAGE {LVCMOS 3.3V} \
    CONFIG.PCW_PRESET_BANK1_VOLTAGE {LVCMOS 1.8V} \
    CONFIG.PCW_UIPARAM_DDR_ENABLE {1} \
    CONFIG.PCW_UIPARAM_DDR_MEMORY_TYPE {DDR 3} \
    CONFIG.PCW_UIPARAM_DDR_PARTNO {MT41J256M16 RE-125} \
    CONFIG.PCW_UIPARAM_DDR_BUS_WIDTH {32 Bit} \
    CONFIG.PCW_UIPARAM_DDR_FREQ_MHZ {533.333333} \
    CONFIG.PCW_UART1_PERIPHERAL_ENABLE {1} \
    CONFIG.PCW_UART1_UART1_IO {MIO 48 .. 49} \
    CONFIG.PCW_EN_CLK0_PORT {1} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
] $ps_cell

# DDR 与固定 MIO 从 PS 模块引出到 Block Design 顶层。
foreach intf_name {DDR FIXED_IO} {
    set ps_intf [get_bd_intf_pins -quiet "processing_system7_0/$intf_name"]
    if {[llength $ps_intf] && ![llength [get_bd_intf_nets -quiet -of_objects $ps_intf]]} {
        make_bd_intf_pins_external $ps_intf
    }
}

set ecg_cell [get_bd_cells -quiet ecg_qrs_axi_0]
if {![llength $ecg_cell]} {
    create_bd_cell -type module -reference ecg_qrs_axi_lite ecg_qrs_axi_0
    set ecg_cell [get_bd_cells ecg_qrs_axi_0]
}
set s_axi [require_one [get_bd_intf_pins -quiet ecg_qrs_axi_0/S_AXI] "ECG AXI-Lite 从接口 S_AXI"]

# AXI Designer Assistance 自动添加互连并连接 PS 主接口、时钟和复位。
if {![llength [get_bd_intf_nets -quiet -of_objects $s_axi]]} {
    apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
        -config [list Master {/processing_system7_0/M_AXI_GP0} Clk {Auto}] $s_axi
}

# 确保 PS AXI 时钟和 ECG 时钟都来自 FCLK0；复位为 PS 输出的低有效复位。
set fclk [require_one [get_bd_pins -quiet processing_system7_0/FCLK_CLK0] "PS FCLK_CLK0"]
set gp0_aclk [require_one [get_bd_pins -quiet processing_system7_0/M_AXI_GP0_ACLK] "PS M_AXI_GP0_ACLK"]
set ecg_aclk [require_one [get_bd_pins -quiet ecg_qrs_axi_0/s_axi_aclk] "ECG AXI 时钟"]
connect_if_free $fclk $gp0_aclk "PS GP0 时钟"
connect_if_free $fclk $ecg_aclk "ECG 外设时钟"

set ps_reset [require_one [get_bd_pins -quiet processing_system7_0/FCLK_RESET0_N] "PS FCLK_RESET0_N"]
set ecg_reset [require_one [get_bd_pins -quiet ecg_qrs_axi_0/s_axi_aresetn] "ECG AXI 低有效复位"]
if {![llength [get_bd_nets -quiet -of_objects $ecg_reset]]} {
    connect_bd_net $ps_reset $ecg_reset
}

# 将 AXI-Lite 寄存器段分配到 PS Data 地址空间的 0x43C0_0000 起始处。
set ps_data [require_one [get_bd_addr_spaces -quiet processing_system7_0/Data] "PS Data 地址空间"]
set ecg_segments [get_bd_addr_segs -quiet -of_objects $s_axi]
if {![llength $ecg_segments]} {
    error "Vivado 没有从 S_AXI 推断出可寻址寄存器段；请检查 RTL 的 AXI 接口属性。"
}
set mapped_segments [get_bd_addr_segs -quiet -of_objects $ps_data]
set ecg_is_mapped 0
foreach seg $ecg_segments {
    if {[lsearch -exact $mapped_segments $seg] >= 0} {
        set ecg_is_mapped 1
    }
}
if {!$ecg_is_mapped} {
    assign_bd_address -offset 0x43C00000 -range 64K \
        -target_address_space $ps_data $ecg_segments
}

regenerate_bd_layout
validate_bd_design
save_bd_design

# 生成 HDL wrapper 并设为综合顶层，为之后综合、导出 XSA 做准备。
set wrapper_files [make_wrapper -files $bd_file -top -force]
set wrapper_file [require_one $wrapper_files "ecg_system_wrapper.v"]
if {![llength [get_files -quiet $wrapper_file]]} {
    add_files -norecurse $wrapper_file
}
set_property top [file rootname [file tail $wrapper_file]] [current_fileset]
update_compile_order -fileset sources_1
generate_target all $bd_file
puts "配置完成：AC7020 PS7、AXI-Lite ECG 外设、地址 0x43C00000 和 HDL wrapper 已准备。"
puts "尚未运行综合、实现、生成 bitstream 或烧录。"
