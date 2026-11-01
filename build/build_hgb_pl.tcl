# 独立候选工程：复用正式领航者生成器，追加HGB，不覆盖正式BD或发布镜像。
set root [file normalize [file join [file dirname [info script]] ..]]
if {$argc != 2} {error "参数：新输出目录 参数ROM目录"}
set out [file normalize [lindex $argv 0]]
set rom [file normalize [lindex $argv 1]]
if {[file exists $out]} {error "输出已存在，拒绝覆盖：$out"}
if {![string match "${root}/tmp/*" $out]} {error "输出必须在项目tmp下"}
create_project hgb_pl $out -part xc7z020clg400-2
set ecg_sample_rate_hz 500
source [file join $root build build_navigator_ecg_system.tcl]
add_files -norecurse [list [file join $root src rtl ecg_hgb_core.sv] [file join $root src rtl ecg_hgb_axi_lite.sv]]
add_files -norecurse [glob $rom/*.mem]
add_files -norecurse [file join $rom hgb_pl_config.vh]
set_property include_dirs [list $rom] [current_fileset]
update_compile_order -fileset sources_1
create_bd_cell -type module -reference ecg_hgb_axi_lite ecg_hgb_axi_0
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list Master {/processing_system7_0/M_AXI_GP0} Clk {Auto}] [get_bd_intf_pins ecg_hgb_axi_0/S_AXI]
assign_bd_address -offset 0x43C10000 -range 64K -target_address_space [get_bd_addr_spaces processing_system7_0/Data] [get_bd_addr_segs -of_objects [get_bd_intf_pins ecg_hgb_axi_0/S_AXI]]
validate_bd_design
save_bd_design
generate_target all [get_files *ecg_system.bd]
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "综合失败"}
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "实现失败"}
open_run impl_1
report_utilization -file $out/utilization.rpt
report_timing_summary -file $out/timing.rpt
if {[get_property SLACK [get_timing_paths -delay_type max -max_paths 1]] < 0} {error "时序未收敛，禁止作为板端部署镜像"}
if {[get_property SLACK [get_timing_paths -delay_type min -max_paths 1]] < 0} {error "保持时序未收敛"}
write_hw_platform -fixed -include_bit -file $out/hgb_pl.xsa
file copy [get_property DIRECTORY [get_runs impl_1]]/ecg_system_wrapper.bit $out/hgb_pl.bit
puts "PASS HGB_PL_BITSTREAM $out"
