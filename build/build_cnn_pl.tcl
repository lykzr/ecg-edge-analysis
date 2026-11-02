# 保留原QRS/HGB外设，新增FP32 CNN；不修改PS7/DDR/MIO配置。
set root [file normalize [file join [file dirname [info script]] ..]]
if {$argc!=3} {error "参数：新输出目录 HGB_ROM目录 HLS_IP目录"}
lassign $argv out rom ip
set out [file normalize $out];set rom [file normalize $rom];set ip [file normalize $ip]
if {[file exists $out] || ![string match "${root}/tmp/*" $out]} {error "需要全新tmp输出目录"}
create_project cnn_pl $out -part xc7z020clg400-2
set ecg_sample_rate_hz 500
source $root/build/build_navigator_ecg_system.tcl
add_files -norecurse [list $root/src/rtl/ecg_hgb_core.sv $root/src/rtl/ecg_hgb_axi_lite.sv]
add_files -norecurse [glob $rom/*.mem]
add_files -norecurse $rom/hgb_pl_config.vh
set_property include_dirs [list $rom] [current_fileset]
set_property ip_repo_paths [list $ip] [current_project]
update_ip_catalog
update_compile_order -fileset sources_1
create_bd_cell -type module -reference ecg_hgb_axi_lite ecg_hgb_axi_0
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list Master {/processing_system7_0/M_AXI_GP0} Clk {Auto}] [get_bd_intf_pins ecg_hgb_axi_0/S_AXI]
assign_bd_address -offset 0x43C10000 -range 64K -target_address_space [get_bd_addr_spaces processing_system7_0/Data] [get_bd_addr_segs -of_objects [get_bd_intf_pins ecg_hgb_axi_0/S_AXI]]
create_bd_cell -type ip -vlnv xilinx.com:hls:cnn_hls:1.0 ecg_cnn_0
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list Master {/processing_system7_0/M_AXI_GP0} Clk {Auto}] [get_bd_intf_pins ecg_cnn_0/s_axi_control]
assign_bd_address -offset 0x43C20000 -range 64K -target_address_space [get_bd_addr_spaces processing_system7_0/Data] [get_bd_addr_segs -of_objects [get_bd_intf_pins ecg_cnn_0/s_axi_control]]
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
if {[get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]<0 || [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]<0} {error "时序未收敛"}
write_hw_platform -fixed -include_bit -file $out/cnn_pl.xsa
file copy [get_property DIRECTORY [get_runs impl_1]]/ecg_system_wrapper.bit $out/cnn_pl.bit
puts "PASS CNN_PL_BITSTREAM $out"
