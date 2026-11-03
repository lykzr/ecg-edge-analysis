# FP32四路全连接候选+工作灯；保留QRS/HGB/INT8，PS7/DDR/MIO/100MHz不变。
set root [file normalize [file join [file dirname [info script]] ..]]
if {$argc!=4} {error "参数：新输出目录 HGB_ROM目录 FP32_IP目录 INT8_IP目录"}
lassign $argv out rom fpip qip
foreach name {out rom fpip qip} {set $name [file normalize [set $name]]}
if {[file exists $out] || ![string match "${root}/tmp/*" $out]} {error "需要全新tmp输出目录"}
create_project cnn_pl $out -part xc7z020clg400-2
set ecg_sample_rate_hz 500
source $root/build/build_navigator_ecg_system.tcl
add_files -norecurse [list $root/src/rtl/ecg_hgb_core.sv $root/src/rtl/ecg_hgb_axi_lite.sv]
add_files -norecurse [glob $rom/*.mem]
add_files -norecurse $rom/hgb_pl_config.vh
set_property include_dirs [list $rom] [current_fileset]
set_property ip_repo_paths [list $fpip $qip] [current_project]
update_ip_catalog
update_compile_order -fileset sources_1
create_bd_cell -type module -reference ecg_hgb_axi_lite ecg_hgb_axi_0
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list Master {/processing_system7_0/M_AXI_GP0} Clk {Auto}] [get_bd_intf_pins ecg_hgb_axi_0/S_AXI]
assign_bd_address -offset 0x43C10000 -range 64K -target_address_space [get_bd_addr_spaces processing_system7_0/Data] [get_bd_addr_segs -of_objects [get_bd_intf_pins ecg_hgb_axi_0/S_AXI]]
foreach {cell vlnv address} {ecg_cnn_0 xilinx.com:hls:cnn_hls:1.0 0x43C20000 ecg_cnn_int8_0 xilinx.com:hls:cnn_int8_hls:1.0 0x43C30000} {
    create_bd_cell -type ip -vlnv $vlnv $cell
    apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list Master {/processing_system7_0/M_AXI_GP0} Clk {Auto}] [get_bd_intf_pins $cell/s_axi_control]
    assign_bd_address -offset $address -range 64K -target_address_space [get_bd_addr_spaces processing_system7_0/Data] [get_bd_addr_segs -of_objects [get_bd_intf_pins $cell/s_axi_control]]
}
# 依据官方AXI GPIO章节：同一个100MHz GP0总线，增加输出寄存器，不改PS引脚。
add_files -norecurse $root/src/rtl/ecg_activity_led.sv
add_files -fileset constrs_1 -norecurse $root/src/constraints/activity_led_navigator_v2.xdc
update_compile_order -fileset sources_1
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 ecg_activity_gpio
set_property -dict [list CONFIG.C_GPIO_WIDTH {1} CONFIG.C_ALL_OUTPUTS {1} CONFIG.C_DOUT_DEFAULT {0x00000000} CONFIG.C_TRI_DEFAULT {0x00000000}] [get_bd_cells ecg_activity_gpio]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list Master {/processing_system7_0/M_AXI_GP0} Clk {Auto}] [get_bd_intf_pins ecg_activity_gpio/S_AXI]
assign_bd_address -offset 0x43C40000 -range 64K -target_address_space [get_bd_addr_spaces processing_system7_0/Data] [get_bd_addr_segs -of_objects [get_bd_intf_pins ecg_activity_gpio/S_AXI]]
create_bd_cell -type module -reference ecg_activity_led ecg_activity_led_0
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins ecg_activity_led_0/clk]
connect_bd_net [get_bd_pins ecg_activity_gpio/s_axi_aresetn] [get_bd_pins ecg_activity_led_0/resetn]
connect_bd_net [get_bd_pins ecg_activity_gpio/gpio_io_o] [get_bd_pins ecg_activity_led_0/active]
create_bd_port -dir O work_led
connect_bd_net [get_bd_pins ecg_activity_led_0/work_led] [get_bd_ports work_led]
validate_bd_design
save_bd_design
make_wrapper -files [get_files *ecg_system.bd] -top -force
update_compile_order -fileset sources_1
generate_target all [get_files *ecg_system.bd]
launch_runs synth_1 -jobs 1
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "综合失败"}
open_run synth_1
report_utilization -hierarchical -file $out/synthesis_hierarchy.rpt
close_design
launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "实现失败"}
open_run impl_1
report_utilization -file $out/utilization.rpt
report_utilization -hierarchical -file $out/utilization_hierarchy.rpt
report_timing_summary -file $out/timing.rpt
if {[get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]<0 || [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]<0} {error "时序未收敛"}
write_hw_platform -fixed -include_bit -file $out/cnn_pl.xsa
file copy [get_property DIRECTORY [get_runs impl_1]]/ecg_system_wrapper.bit $out/cnn_pl.bit
puts "PASS CNN_FAST_LED_BITSTREAM $out"
